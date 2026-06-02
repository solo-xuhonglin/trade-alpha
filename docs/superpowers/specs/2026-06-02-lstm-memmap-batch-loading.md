# LSTM 训练 Memmap 分批加载设计

## 背景

LSTM 模型训练时，`create_sequences()` 将所有股票多年数据一次性生成为 `(n_samples, seq_len, n_features)` 的 3D 数组，全部驻留在内存中。当训练范围覆盖 2018-2025（8 年）且股票池较大时，X_3d 数组可能占用 10GB+ 内存，加上中间 DataFrame 和训练集张量，峰值内存可达 20GB+，导致内存不足。

## 目标

通过 NumPy Memmap 将序列数据存储到磁盘，训练时按 batch 按需读取，将峰值内存从 ~21GB 降至 ~2.5GB，同时保持训练速度接近纯内存水平。

## 设计概要

在模型配置中新增 `use_memmap` 开关（默认 `False`），启用时：
1. `create_sequences()` 改为写入 memmap 文件而非在内存中构建列表
2. 自定义 PyTorch Dataset 从 memmap 逐 batch 读取
3. 训练结束后自动清理临时文件

## 涉及文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `dao/model_config.py` | 新增字段 | `use_memmap: bool = False` |
| `dao/execution.py` | 新增字段 | `ModelSnapshotEmbed.use_memmap: bool = False` |
| `models/training/config.py` | 参数+构造函数 | create_config 接受 use_memmap |
| `api/routers/model_configs.py` | 透传 | ConfigCreate/ConfigUpdate + config_to_dict |
| `models/lstm/normalizer.py` | 新增函数 | `create_sequences_memmap()` |
| `models/lstm/classifier.py` | 新增类+修改train | `MemmapSequenceDataset` + 条件分支 |
| `frontend ModelConfigView.vue` | UI + 数据 | form默认值、编辑回填、LSTM参数区域加开关 |

## 详细设计

### 1. 数据模型变更

**`ModelConfig`**（`dao/model_config.py`）新增字段：

```python
use_memmap: bool = False
```

默认 `False` 保持现有行为。

**`ModelSnapshotEmbed`**（`dao/execution.py`）新增相同字段，用于训练结果快照回现：

```python
use_memmap: bool = False
```

训练结果查看时，快照数据会包含该字段，用户可知道该次训练是否启用了 memmap 加速。

### 1b. API 层变更

**`api/routers/model_configs.py`** 三处改动：

- `ConfigCreate` 新增 `use_memmap: Optional[bool] = None`
- `ConfigUpdate` 新增 `use_memmap: Optional[bool] = None`
- `config_to_dict()` 新增 `"use_memmap": c.use_memmap`
- create 端点新增 `use_memmap=body.use_memmap or False`

`update_config` 端点使用 `body.model_dump(exclude_unset=True)` 自动透传，无需手动处理。

### 1c. 前端配置页面变更

**`frontend/src/views/ModelConfigView.vue`**：

`defaultForm` 添加默认值：

```typescript
use_memmap: false,
```

`lstmRecommendedParams` 添加：

```typescript
use_memmap: false,
```

`openDialog` 编辑模式回填：

```typescript
use_memmap: item.use_memmap ?? false,
```

UI 模板中，在 LSTM 参数区的"训练控制"分组下加一个开关：

```html
<v-row>
  <v-col cols="12">
    <v-switch v-model="form.use_memmap" label="启用磁盘映射（use_memmap）"
      hint="将序列数据映射到磁盘，大幅降低内存占用（适合大范围训练）"
      persistent-hint color="primary"></v-switch>
  </v-col>
</v-row>
```

放在 `batch_size` / `val_size` 那一行的后面。

### 2. `create_sequences_memmap()` 函数

位于 `normalizer.py`，与现有 `create_sequences` 并列。

**流程：**

```
第一遍扫描（低内存，仅计数）：
  逐股票遍历 DataFrame
  过滤 NaN，统计每只股票的有效序列数
  累计 total_seqs

创建 memmap 文件：
  X_memmap = np.memmap(path, dtype='float64', mode='w+',
                       shape=(total_seqs, seq_len, n_features))

第二遍扫描（填充数据）：
  逐股票遍历，重复相同的计算逻辑
  将 X_seq 写入 memmap[pos]，y 写入 y_array，date 写入 dates_array

排序：
  sorted_idx = np.argsort(dates_array)  # 按日期全局排序
  保存 sorted_idx 到 .npy 文件

返回 MemmapData 对象（包含路径、总行数、形状等信息）
```

**峰值内存**：两遍扫描期间仅保留单只股票的数据（~2000 行 × 65 列 ≈ 1MB），其余数据从 DataFrame 中读取后逐序列写入 memmap，不累积。

**临时文件布局：**

```
models/temp/{training_id}/
├── X_3d.dat          # memmap 数据文件
├── sorted_idx.npy    # 全局排序索引（~几 MB）
├── y_2d.npy          # 标签数组（小）
├── dates.npy         # 日期数组（小）
└── info.json         # 元数据：shape、dtype、total_seqs 等
```

### 3. `MemmapSequenceDataset`

位于 `classifier.py`，继承 `torch.utils.data.Dataset`。

```python
class MemmapSequenceDataset(Dataset):
    def __init__(self, memmap_dir, y_array, sorted_idx, mask):
        info = json.load(open(f"{memmap_dir}/info.json"))
        self.X = np.memmap(f"{memmap_dir}/X_3d.dat", dtype='float64', mode='r',
                           shape=(info["total_seqs"], info["seq_len"], info["n_features"]))
        self.sorted_idx = sorted_idx
        self.y = y_array
        self.indices = np.where(mask)[0]

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        real_idx = self.sorted_idx[self.indices[idx]]
        return torch.FloatTensor(self.X[real_idx]), torch.LongTensor([self.y[real_idx]])[0]
```

### 4. `LSTMClassifier.train()` 分支逻辑

```python
if config.use_memmap:
    memmap_dir = f"models/temp/{training_id}/"
    data = create_sequences_memmap(
        combined_df, config.feature_fields, target_names,
        seq_len, normalization_window, memmap_dir
    )
    y_2d = np.load(f"{memmap_dir}/y_2d.npy")
    dates = np.load(f"{memmap_dir}/dates.npy")
    sorted_idx = np.load(f"{memmap_dir}/sorted_idx.npy")
else:
    X_3d, y_2d, dates = create_sequences(...)  # 原有逻辑
    X_3d = np.nan_to_num(X_3d)
```

后续共用逻辑（label mapping、train/val split）保持不变。差异仅在 DataLoader 构造：

```python
if config.use_memmap:
    train_dataset = MemmapSequenceDataset(memmap_dir, y_2d, sorted_idx, train_mask)
else:
    X_train = X_3d[train_mask]
    y_train = y_mapped[train_mask]
    train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train))

train_loader = DataLoader(train_dataset, batch_size=config.lstm_batch_size, shuffle=True)
```

验证集保持一次加载（~20% 数据，~2GB，可接受）。

### 5. 清理机制

```python
import atexit, shutil, signal

def _cleanup(memmap_dir):
    if os.path.exists(memmap_dir):
        shutil.rmtree(memmap_dir, ignore_errors=True)

# Python 正常退出
atexit.register(_cleanup, memmap_dir)
# 信号处理（SIGTERM）
signal.signal(signal.SIGTERM, lambda *args: (_cleanup(memmap_dir), sys.exit(1)))
```

### 6. 评估阶段的适配

训练后的模型评估（第 281-306 行）需要全量 X_3d 做 forward pass：

```python
if config.use_memmap:
    X_3d = np.memmap(...)[sorted_idx]  # 触发读取到内存
    X_3d = X_3d[valid_mask]  # 过滤无效样本
```

这一步会将全部序列读入内存（~10GB），但这是训练结束后的单次操作，不做 backward，内存可即时释放。

## 内存对比

| 阶段 | 原逻辑 | Memmap 逻辑 |
|------|--------|-------------|
| 数据加载 (combined_df) | ~240 MB | ~240 MB |
| 序列创建 (X_list) | ~10 GB 列表 | ~1 MB（逐序列写入） |
| 训练 - 训练集 | ~8.5 GB 张量 | ~0（memmap + page cache） |
| 训练 - 验证集 | ~2.1 GB 张量 | ~2.1 GB 张量 |
| 评估 (forward pass) | ~0（已加载） | ~10 GB 单次读取后释放 |
| **峰值内存** | **~21 GB** | **~2.5 GB** |

## 速度影响

- **预处理**：多一次全量扫描 + 文件写入，约增加 5-10 秒
- **第一 epoch**：DataLoader 遍历 memmap → 触发磁盘读取，SSD 顺序读 ~500MB/s，每个 batch ~8MB，延迟约 4ms/batch
- **后续 epoch**：数据已缓存在 OS 页缓存中，速度 ≈ 纯内存
- **8 epoch 总耗时增加**：约 15-30 秒
# LSTM Memmap 分批加载实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 LSTM 训练中通过 NumPy Memmap 将序列数据存储到磁盘，训练时按 batch 按需读取，降低峰值内存 ~21GB → ~2.5GB，并在模型配置中提供 `use_memmap` 开关。

**Architecture:** 后端分层修改：DAO 模型 → 配置服务 → API 路由，然后 normalizer 新增 `create_sequences_memmap()`，classifier 新增 `MemmapSequenceDataset` 并在 `train()` 中根据 `config.use_memmap` 分支选择。前端模型配置页 LSTM 参数区加开关。

**Tech Stack:** Python 3.14+, NumPy, PyTorch, FastAPI, Vue 3 + Vuetify

---

### Task 1: 后端数据模型新增 use_memmap 字段

**Files:**
- Modify: `backend/src/trade_alpha/dao/model_config.py:110`
- Modify: `backend/src/trade_alpha/dao/execution.py:96`

- [ ] **Step 1: ModelConfig 新增 use_memmap**

在 `dao/model_config.py` 的 `lstm_normalization_window` 和 `lstm_weight_decay` 之间添加：

```python
use_memmap: bool = False
```

- [ ] **Step 2: ModelSnapshotEmbed 新增 use_memmap**

在 `dao/execution.py` 的 `ModelSnapshotEmbed` 类的 `lstm_normalization_window` 和 `lstm_weight_decay` 之间添加：

```python
use_memmap: bool = False
```

---

### Task 2: 配置服务层新增 use_memmap 参数

**Files:**
- Modify: `backend/src/trade_alpha/models/training/config.py:90`

- [ ] **Step 1: create_config 参数列表添加 use_memmap**

在 `lstm_normalization_window` 参数后面添加：

```python
use_memmap: bool = False,
```

- [ ] **Step 2: ModelConfig 构造函数添加**

在 config 构造函数的 `lstm_normalization_window=lstm_normalization_window,` 后面添加：

```python
use_memmap=use_memmap,
```

---

### Task 3: API 路由层透传 use_memmap

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/model_configs.py`

在 `ConfigCreate`、`ConfigUpdate`、`config_to_dict`、create 端点共 4 处添加。

- [ ] **Step 1: ConfigCreate 新增字段**

```python
use_memmap: Optional[bool] = None
```

放在 `lstm_normalization_window` 和 `lstm_weight_decay` 之间。

- [ ] **Step 2: ConfigUpdate 新增字段**

```python
use_memmap: Optional[bool] = None
```

放在 `lstm_normalization_window` 和 `lstm_weight_decay` 之间。

- [ ] **Step 3: config_to_dict 新增字段**

```python
"use_memmap": c.use_memmap,
```

放在 `"lstm_normalization_window": c.lstm_normalization_window,` 后面。

- [ ] **Step 4: create 端点添加 use_memmap**

```python
use_memmap=body.use_memmap or False,
```

放在 `lstm_normalization_window=body.lstm_normalization_window or 300,` 后面。

`update_config` 端点使用 `body.model_dump(exclude_unset=True)` 自动透传，无需修改。

---

### Task 4: normalizer 新增 create_sequences_memmap()

**Files:**
- Create: 不新建文件（在 `backend/src/trade_alpha/models/lstm/normalizer.py` 中新增函数）

- [ ] **Step 1: 在 create_sequences 后面新增 create_sequences_memmap 函数**

```python
import os, json
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional


def create_sequences_memmap(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
    normalization_window: int,
    memmap_dir: str,
) -> Tuple[int, int]:
    """Create sequences and write directly to memmap files.

    Two-pass approach: first pass counts sequences, second pass fills memmap.
    Returns (total_seqs, n_features).
    """
    os.makedirs(memmap_dir, exist_ok=True)

    # First pass: count sequences
    total_seqs = 0
    nan_skip = 0
    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        if len(values) < normalization_window:
            continue
        for i in range(normalization_window - 1, len(values)):
            window = values[i - normalization_window + 1 : i + 1]
            seq = window[-sequence_length:]
            label = labels[i]
            if np.isnan(seq).any() or np.isnan(label).any():
                nan_skip += 1
                continue
            total_seqs += 1

    n_features = len(feature_fields)
    n_targets = len(target_names)

    # Create memmap files
    seq_path = os.path.join(memmap_dir, "X_3d.dat")
    X_memmap = np.memmap(seq_path, dtype="float64", mode="w+",
                         shape=(total_seqs, sequence_length, n_features))

    y_array = np.zeros((total_seqs, n_targets), dtype=np.float64)
    dates_array = np.zeros(total_seqs, dtype="U10")

    # Second pass: fill memmap
    idx = 0
    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        dates = group["trade_date"].values
        if len(values) < normalization_window:
            continue
        for i in range(normalization_window - 1, len(values)):
            window = values[i - normalization_window + 1 : i + 1]
            label = labels[i]
            date = dates[i]
            seq = window[-sequence_length:]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue
            mean = np.nanmean(window, axis=0)
            std = np.nanstd(window, axis=0)
            std[std == 0] = 1.0
            X_seq = ((seq - mean) / std).astype(np.float64)
            X_memmap[idx] = X_seq
            y_array[idx] = label
            dates_array[idx] = str(date)
            idx += 1

    X_memmap.flush()

    # Sort by date
    sorted_idx = np.argsort(dates_array)
    np.save(os.path.join(memmap_dir, "sorted_idx.npy"), sorted_idx)
    np.save(os.path.join(memmap_dir, "y_2d.npy"), y_array)
    np.save(os.path.join(memmap_dir, "dates.npy"), dates_array)

    info = {
        "total_seqs": total_seqs,
        "seq_len": sequence_length,
        "n_features": n_features,
        "n_targets": n_targets,
        "dtype": "float64",
    }
    with open(os.path.join(memmap_dir, "info.json"), "w") as f:
        json.dump(info, f)

    return total_seqs, n_features
```

- [ ] **Step 2: 验证语法正确**

```bash
cd backend; .venv\Scripts\python -c "import py_compile; py_compile.compile('src/trade_alpha/models/lstm/normalizer.py', doraise=True); print('OK')"
```

Expected: `OK`

---

### Task 5: classifier 新增 MemmapSequenceDataset 和 train 分支

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/classifier.py`

- [ ] **Step 1: 新增 MemmapSequenceDataset 类**

在 `LSTMModel` 类之后、`TEMPERATURE` 常量之前添加：

```python
import json


class MemmapSequenceDataset(torch.utils.data.Dataset):
    """PyTorch Dataset that reads sequences from memmap on demand."""

    def __init__(self, memmap_dir: str, y_array: np.ndarray, sorted_idx: np.ndarray, mask: np.ndarray):
        with open(os.path.join(memmap_dir, "info.json")) as f:
            info = json.load(f)
        self.X = np.memmap(
            os.path.join(memmap_dir, "X_3d.dat"),
            dtype="float64", mode="r",
            shape=(info["total_seqs"], info["seq_len"], info["n_features"]),
        )
        self.sorted_idx = sorted_idx
        self.y = y_array
        self.indices = np.where(mask)[0]

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, idx: int):
        real_idx = self.sorted_idx[self.indices[idx]]
        X_seq = torch.FloatTensor(self.X[real_idx].copy())
        y_val = int(self.y[real_idx])
        return X_seq, torch.LongTensor([y_val])[0]
```

- [ ] **Step 2: 在 train() 中修改数据加载分支**

修改 `LSTMClassifier.train()` 第 82-89 行（`pd.concat` 之后的 `create_sequences` 调用附近）：

```python
        if not all_dfs:
            raise ValueError("No available data")

        combined_df = pd.concat(all_dfs, ignore_index=True)
        combined_df = combined_df.sort_values('trade_date')

        if config.use_memmap:
            os.makedirs("models/temp", exist_ok=True)
            memmap_dir = f"models/temp/{task_id}/"
            total_seqs, n_features = create_sequences_memmap(
                combined_df, config.feature_fields, target_names,
                seq_len, normalization_window, memmap_dir,
            )
            y_2d = np.load(os.path.join(memmap_dir, "y_2d.npy"))
            dates = np.load(os.path.join(memmap_dir, "dates.npy"))
            sorted_idx = np.load(os.path.join(memmap_dir, "sorted_idx.npy"))
            self.input_size = n_features
            # For nan_to_num - memmap mode handles NaN at creation time
            valid_mask = ~np.isnan(y_2d).any(axis=1)
            if valid_mask.sum() == 0:
                raise ValueError("No valid samples after NaN filtering")
        else:
            X_3d, y_2d, dates = create_sequences(
                combined_df, config.feature_fields, target_names,
                sequence_length=seq_len,
                normalization_window=normalization_window,
            )
            if len(X_3d) == 0:
                raise ValueError("No sequences created from available data")
            self.input_size = X_3d.shape[2]
            X_3d = np.nan_to_num(np.array(X_3d, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
            y_2d = np.array(y_2d, dtype=np.float64)
            valid_mask = ~np.isnan(y_2d).any(axis=1)
            X_3d, y_2d, dates = X_3d[valid_mask], y_2d[valid_mask], dates[valid_mask]
```

- [ ] **Step 3: 修改 normalized_data_analysis 适配 memmap**

第 96-108 行的 `normalized_data_analysis` 部分需要适配 memmap 模式：

```python
        if config.use_memmap:
            normalized_2d = np.memmap(
                os.path.join(memmap_dir, "X_3d.dat"),
                dtype="float64", mode="r",
                shape=(total_seqs, seq_len, n_features),
            )[sorted_idx][valid_mask][:, -1, :]
        else:
            normalized_2d = X_3d[:, -1, :]
```

- [ ] **Step 4: 修改 DataLoader 构造分支**

找到第 137 行循环内的数据加载部分，修改为：

```python
            if config.use_memmap:
                y_i = y_2d[:, target_idx].astype(int)
                unique_labels = sorted(set(y_i))
                label_map = {j: label for j, label in enumerate(unique_labels)}
                reverse_map = {label: j for j, label in label_map.items()}
                y_mapped = np.array([reverse_map[v] for v in y_i])

                train_dataset = MemmapSequenceDataset(
                    memmap_dir, y_mapped, sorted_idx, train_mask
                )
            else:
                y_i = y_2d[:, target_idx].astype(int)
                unique_labels = sorted(set(y_i))
                label_map = {j: label for j, label in enumerate(unique_labels)}
                reverse_map = {label: j for j, label in label_map.items()}
                y_mapped = np.array([reverse_map[v] for v in y_i])

                X_train, X_val = X_3d[train_mask], X_3d[val_mask]
                y_train, y_val = y_mapped[train_mask], y_mapped[val_mask]
                train_dataset = torch.utils.data.TensorDataset(
                    torch.FloatTensor(X_train), torch.LongTensor(y_train)
                )

            train_loader = torch.utils.data.DataLoader(
                train_dataset,
                batch_size=config.lstm_batch_size, shuffle=True,
            )
```

验证集 `X_val_tensor` 和 `y_val_tensor` 保持原有逻辑（memmap 模式也需要取验证集）：

```python
            # 放在 train_dataset 构造之后、train_loader 之前
            if config.use_memmap:
                val_indices = np.where(val_mask)[0]
                val_real_idx = sorted_idx[val_indices]
                X_val_np = np.memmap(
                    os.path.join(memmap_dir, "X_3d.dat"),
                    dtype="float64", mode="r",
                    shape=(total_seqs, seq_len, n_features),
                )[val_real_idx]
                y_val = y_mapped[val_mask]
                y_val_original = y_2d[val_mask, target_idx].astype(int)
            else:
                X_val = X_3d[val_mask]
                y_val = y_mapped[val_mask]
                y_val_original = y_2d[val_mask, target_idx].astype(int)
                X_val_np = X_val

            X_val_tensor = torch.FloatTensor(X_val_np).to(device)
            y_val_tensor = torch.LongTensor(y_val).to(device)
```

- [ ] **Step 5: 修改评估阶段的适配**

第 281-306 行的模型评估（全量 forward pass）需要适配 memmap：

```python
        for target_idx, target in enumerate(target_names):
            y_true = y_2d[:, target_idx].astype(int)
            model = self.models[target].eval()
            with torch.no_grad():
                if config.use_memmap:
                    X_eval_full = np.memmap(
                        os.path.join(memmap_dir, "X_3d.dat"),
                        dtype="float64", mode="r",
                        shape=(total_seqs, seq_len, n_features),
                    )[sorted_idx][valid_mask]
                else:
                    X_eval_full = X_3d
                X_eval = torch.FloatTensor(X_eval_full).cpu()
                logits = model(X_eval)
                ...
```

- [ ] **Step 6: 添加清理机制**

在 `train()` 方法返回之前添加清理代码：

```python
        # Cleanup memmap temp files
        if config.use_memmap and os.path.exists(memmap_dir):
            import shutil
            shutil.rmtree(memmap_dir, ignore_errors=True)
```

也在函数开头添加 atexit 注册（但在子进程模式下，atexit 可能不够可靠，`try/finally` 更安全）：

```python
        if config.use_memmap:
            os.makedirs("models/temp", exist_ok=True)
            memmap_dir = f"models/temp/{task_id}/"
```

并在整个 `train()` 方法外包一层 `try/finally`：

在 `train()` 的最后（`return metrics` 之后），用 finally 确保清理：

实际做法：在返回前的所有异常路径和正常路径都保证清理。最简单的方式是把清理放在一个 finally 块中。

将整个 `try/except` 改成 `try/except/finally`，或者在训练循环结束后、return 之前清理。

---

### Task 6: 前端模型配置页加 use_memmap 开关

**Files:**
- Modify: `frontend/src/views/ModelConfigView.vue`

- [ ] **Step 1: defaultForm 添加 use_memmap**

```typescript
use_memmap: false,
```

放在 `early_stopping_patience: 10,` 后面。

- [ ] **Step 2: lstmRecommendedParams 添加 use_memmap**

```typescript
use_memmap: false,
```

- [ ] **Step 3: openDialog 编辑模式回填**

```typescript
use_memmap: item.use_memmap ?? false,
```

- [ ] **Step 4: UI 模板添加开关**

在 LSTM 参数区的"训练控制"分组下，`batch_size` / `val_size` 那一行后面添加：

```html
<v-row>
  <v-col cols="12">
    <v-switch v-model="form.use_memmap" label="启用磁盘映射（use_memmap）"
      hint="将序列数据映射到磁盘，大幅降低内存占用（适合大范围训练）"
      persistent-hint color="primary"></v-switch>
  </v-col>
</v-row>
```

---

### Task 7: 编译验证

- [ ] **Step 1: 后端编译检查**

```bash
cd backend; .venv\Scripts\python -c "
import py_compile
files = [
    'src/trade_alpha/dao/model_config.py',
    'src/trade_alpha/dao/execution.py',
    'src/trade_alpha/models/training/config.py',
    'src/trade_alpha/api/routers/model_configs.py',
    'src/trade_alpha/models/lstm/normalizer.py',
    'src/trade_alpha/models/lstm/classifier.py',
]
for f in files:
    py_compile.compile(f, doraise=True)
print('All files compile OK')
"
```

Expected: `All files compile OK`

- [ ] **Step 2: 前端类型检查**

```bash
cd frontend; npx vue-tsc --noEmit 2>&1 | head -30
```

Expected: No type errors

- [ ] **Step 3: 重启后端服务验证**

```bash
cd d:\projects\trade-alpha; .\service.bat restart
```
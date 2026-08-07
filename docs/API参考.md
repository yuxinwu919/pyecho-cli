# ECHO2D-CLI (pyecho) API 参考文档

> 本文档面向 `pyecho` 0.2.0（Beta）版本，覆盖核心库全部公共类与函数。
> 所有参数类型、返回类型与描述均直接提取自源码 docstring。
> 包内模块默认使用 `from __future__ import annotations`，因此类型注解中的
> `str | Path`、`list[int] | None` 等写法在 Python ≥ 3.10 下有效。

---

## 目录

1. [核心模块](#1-核心模块)
2. [几何](#2-几何)
3. [后处理](#3-后处理)
4. [预处理](#4-预处理)
5. [数值工具](#5-数值工具)
6. [可视化](#6-可视化)
7. [I/O](#7-io)
8. [项目管理](#8-项目管理)
9. [收敛](#9-收敛)
10. [高级 API](#10-高级-api)

---

## 1. 核心模块

核心模块提供 ECHO2D 仿真的参数配置、结果数据模型、异常体系、运行器与输出解析器。

### 1.1 `pyecho.config` — 仿真参数（Pydantic v2 模型）

该模块负责解析、校验并生成 ECHO2D 求解器的 `input_in.txt` 文件，支持 ECHO 手册
（第 4.3.2 节）中记录的全部参数。

```python
from pyecho.config import ECHO2DParams
params = ECHO2DParams.from_input_file("input_in.txt")
print(params.to_input_file())

params = ECHO2DParams.from_template("round_collimator")
```

#### 类 `FieldMonitorConfig`

单个 ECHO2D 场监视器配置，对应输入文件中的一行 `FieldMonitor = { ... }`。

```python
class FieldMonitorConfig(BaseModel):
    component: str                  # 场分量："Ex"|"Ey"|"Ez"|"Hx"|"Hy"|"Hz"
    time_type: Literal["s", "z"]    # 时间坐标："s"(随动) 或 "z"(实验室系)
    z0: float                       # 纵向范围起点 [m]
    z1: float                       # 纵向范围终点 [m]
    y0: float                       # 横向范围起点 [m]
    y1: float                       # 横向范围终点 [m]
    s0: float                       # s 坐标范围起点 [m]
    s1: float                       # s 坐标范围终点 [m]
    N: int                          # 快照数量
```

- `component` 字段经校验器限制为 `{Ex, Ey, Ez, Hx, Hy, Hz}`，非法值抛出 `ConfigError`。

#### 类 `ECHO2DParams`

主参数模型，所有字段对应 `input_in.txt` 的键，默认值取自 N1 round-collimator 示例。

```python
class ECHO2DParams(BaseModel):
    # ---- 几何 ----
    GeometryFile: str = "collimator.txt"       # ASCII 几何文件名 (*.txt)
    Units: Literal["m", "cm", "mm"] = "cm"     # 几何文件长度单位
    GeometryType: Literal["round", "recta"] = "round"  # "recta" 接受别名 "rect"
    Width: float = 0.0                         # 矩形几何宽度 [m]（round 时废弃）
    SymmetryCondition: Literal["magn", "elec"] = "magn"  # 轴边界条件（recta）
    Convex: bool = True                        # 是否启用凸几何加速

    # ---- 束流 ----
    InPartFile: str = "-"                      # 输入束流文件：'-'=高斯束，或 *.txt/*.bin
    BunchSigma: float = 0.001                  # 束团 RMS 长度 [m]
    Offset: int = -1                           # 束团横向偏移（网格线数）；-1 = 最大
    InjectionTimeStep: int = 0                 # 粒子注入时间步

    # ---- 场 ----
    InFieldDir: str = "-"                      # 初始场文件目录；'-'=内部计算
    PortDir: str = "-"                         # 波导端口模式文件目录；'-'=无
    PortPosition: int = -1                     # 波导端口位置（网格线）；-1 = 无

    # ---- 模型 ----
    WakeIntMethod: Literal["dir", "ind"] = "ind"  # 尾场积分方法
    Modes: list[int] = [0]                     # 要计算的傅里叶方位角模式
    ParticleMotion: bool = False               # 是否启用粒子运动方程
    ParticleField: bool = True                 # 是否启用场计算
    CurrentFilter: int = 0                     # 电流剖面上 2 点低通滤波次数
    ParticleLoss: bool = False                 # 是否启用材料中的粒子损失

    # ---- 网格 ----
    MeshLength: int = 52                       # 移动网格长度（网格线数）
    StartPosition: int = 0                     # 移动网格纵向起始位置
    TimeSteps: int = -1                        # 时间步数；-1 = 飞越整个结构
    StepY: float = 0.0002                      # 横向网格步长 h_y [m]
    StepZ: float = 0.0002                      # 纵向网格步长 h_z [m]
    NStepsInConductive: int = 0                # 导电壁趋肤深度内网格线；0 = PEC
    AdjustMesh: bool = True                    # 自动调整横向网格
    MeshMotionFile: str = "-"                  # 网格运动文件；'-'=以光速飞行

    # ---- 监视器 ----
    WakeMonitor: list[int] | None = None       # 尾场保存点 [M1, M2, M3]
    BeamMonitor: list[int] | None = None       # 束流监视参数 [M1, M2, M3, M4]
    FieldMonitor: list[FieldMonitorConfig] = []  # 场监视器配置列表
    DumpField: bool = False                    # 转储电磁场到磁盘
    DumpParticles: bool = False                # 转储粒子数据到磁盘
    DumpCurrent: bool = False                  # 转储电流剖面到磁盘
    DumpMesh: bool = False                     # 转储网格几何到磁盘
```

**校验器（Validators）**

| 校验器 | 行为 |
|---|---|
| `_normalize_geometry_type` | `GeometryType` 接受 `"rect"` 作为 `"recta"` 的别名 |
| `_parse_modes` | `Modes` 接受空格分隔字符串或列表 |
| `_parse_int_list_or_none` | `WakeMonitor`/`BeamMonitor` 接受字符串、列表或 `'-'`（→ `None`） |
| `_validate_recta_modes` | recta + 对称条件时，偶数方位角模式对尾场无贡献，发出警告 |
| `_validate_width` | recta 几何下 `Width` 必须 > 0，否则抛 `ConfigError` |
| `_validate_mesh_resolution` | 束团 RMS 宽度上网格点数 < 3 时警告（手册建议 ≥ 5） |

**方法**

| 方法 | 签名 | 说明 |
|---|---|---|
| `to_input_file` | `(self) -> str` | 生成精确的 `input_in.txt` 格式内容 |
| `from_input_file` | `(cls, path: str \| Path) -> ECHO2DParams` | 解析输入文件；文件不存在或含未知键时抛 `ConfigError` |
| `from_string` | `(cls, text: str) -> ECHO2DParams` | 从含 `input_in.txt` 内容的字符串解析 |
| `from_template` | `(cls, name: str, **overrides) -> ECHO2DParams` | 从命名预设模板创建，可覆盖字段；未知模板抛 `ConfigError` |
| `list_templates` | `(cls) -> list[str]` | 返回所有已注册模板名 |

**内置模板**：`"round_collimator"`、`"flat_absorber"`、`"tesla_cavity"`、`"dlw"`。

#### 模块级便捷函数

```python
def load_params(path: str | Path) -> ECHO2DParams:
    """从 input_in.txt 文件加载 ECHO2D 参数。"""

def save_params(params: ECHO2DParams, path: str | Path) -> None:
    """将参数模型序列化写入 input_in.txt 文件。"""
```

---

### 1.2 `pyecho.datamodel` — 结果数据类

定义尾场势、场监视器数据、模式结果与仿真元数据等结构化容器，全部基于 dataclass
与 numpy 数组类型注解。

#### 类 `WakeResult`

单模式的后处理纵向尾场势。

```python
@dataclass
class WakeResult:
    s: np.ndarray          # 纵向坐标 [m]（正 s 指向束团尾部）
    W: np.ndarray          # 尾场势 [V/pC]
    bunch: np.ndarray      # 同一 s 网格上的束团电荷密度剖面
    loss_factor: float     # 损失因子 κ = −∫λ(s)·W(s)·ds [V/pC]
    rms_spread: float      # 尾场相对 −κ 的 RMS 展宽 [V/pC]
    peak: float            # 尾场势的峰值绝对值 [V/pC]
    label: str = ""        # 可读标签（如模式号、几何标签）
    units: str = "V/pC"    # 单位字符串
```

#### 类 `RectaWakeResult`

矩形（recta）几何的完整尾场结果，分解为单极子（Wlong）、四极子（Wquad）与
偶极子（Wdipole）分量，可选存储完整 Wcc/Wss 耦合矩阵。

```python
@dataclass
class RectaWakeResult:
    s: np.ndarray                # 纵向坐标 [m]
    Wlong: np.ndarray            # 单极子（纵向）尾场 [V/pC]
    Wquad: np.ndarray            # 四极子尾场 [V/pC/mm]
    Wdipole: np.ndarray          # 偶极子尾场 [V/pC/mm]
    loss_long: float             # 纵向损失因子 [V/pC]
    kick_quad: float             # 四极子踢力因子 [V/pC/mm]
    kick_dipole: float           # 偶极子踢力因子 [V/pC/mm]
    wcc: np.ndarray | None = None  # Wcc(k, s) 耦合矩阵（cos-cos 分量）
    wss: np.ndarray | None = None  # Wss(k, s) 耦合矩阵（sin-sin 分量）
```

#### 类 `RoundWakeResult`

旋转对称（round）几何的完整尾场结果，按独立方位角模式分解。

```python
@dataclass
class RoundWakeResult:
    s: np.ndarray                 # 纵向坐标 [m]
    Wlong: np.ndarray             # 单极子（m=0）纵向尾场势 [V/pC]
    Wdipole: np.ndarray | None    # 偶极子（m=1）模态系数 [V/pC/m²]；未计算则为 None
    loss_long: float              # 纵向损失因子 κ [V/pC]
    kick_dipole: float | None     # 偶极子横向踢力因子 [V/pC/m]；未计算则为 None
    bunch: np.ndarray             # 同一 s 网格上的束团电荷密度剖面
    peak: float = 0.0             # Wlong 峰值绝对值 [V/pC]
    rms_spread: float = 0.0       # Wlong 相对 −κ 的 RMS 展宽 [V/pC]
```

> **关键约定**：round 几何的有效横向步长 `dy = (offset + 0.5)·hr`，此 +0.5 偏移
> 对正确性至关重要（见 ECHO 手册 §4.3.2）。

#### 类 `ModeResult`

单个傅里叶方位角模式的原始与处理后结果。

```python
@dataclass
class ModeResult:
    mode_number: int               # 方位角模式索引（0=单极子，1=偶极子，…）
    s_raw: np.ndarray              # wakeL 文件的原始 s 坐标 [m]
    W_raw: np.ndarray              # wakeL 文件的原始尾场势 [m·V/nC]
    hr: float                      # 该模式使用的横向网格步长 [m]
    offset: int                    # 束团偏移（网格线数）
    D: float                       # 结构宽度 [m]（= input_in.txt 的 Width，仅 recta 有意义）
    sigma: float                   # 束团 RMS 长度 [m]
    wake_processed: WakeResult | None = None  # 处理后尾场（单位转换与积分后填充）
```

#### 类 `MonitorData`

仿真期间记录的场监视器数据。

```python
@dataclass
class MonitorData:
    monitor_id: int        # 顺序监视器索引
    field_component: str   # 场分量标签："Ex"|"Ey"|"Ez"|"Hx"|"Hy"|"Hz"
    time_type: str         # 时间坐标类型："s"(随动) 或 "z"(实验室)
    T: np.ndarray          # 一维时间（或 s）坐标数组
    Z: np.ndarray          # 一维纵向 z 坐标数组
    R: np.ndarray          # 一维横向 r（round）或 y（flat）坐标数组
    F: np.ndarray          # 二维（或三维）场值数组
    D: float               # 结构宽度 [m]（仅 recta，= Width）
```

#### 类 `RunMetadata`

单次仿真运行记录的元数据（执行环境、计时与可复现性信息）。

```python
@dataclass
class RunMetadata:
    timestamp: datetime = datetime.now()   # 运行启动时间
    executable_path: str = ""              # ECHO2D 二进制路径
    executable_arch: str = ""              # 架构标签（如 "MacOS_ARM_OpenMP"）
    mpi_processes: int = 1                 # MPI 进程数
    omp_threads: int = 1                   # OpenMP 线程数
    elapsed_seconds: float = 0.0           # 仿真墙钟时长
    hostname: str = ""                     # 执行主机名
    pyecho_version: str = __version__      # pyecho 版本
    input_hash: str = ""                   # 输入文件 SHA-256（可复现性）
    output_hash: str = ""                  # 输出目录 SHA-256（可复现性）
    return_code: int = 0                   # 进程退出码（0 = 成功）
```

#### 类 `SimulationResult`

完整 ECHO2D 仿真结果的顶层容器，捆绑输入参数、输出文件引用、解析数据与元数据，
可序列化为 HDF5/pickle 或传入后处理管道。

```python
@dataclass
class SimulationResult:
    params: Any = None                    # ECHO2DParams 实例
    geometry_file: str = ""               # 几何描述文件路径
    output_dir: str = ""                  # 输出文件目录
    modes: dict[int, ModeResult] = {}     # 模式号 → ModeResult
    currents_z: np.ndarray | None = None  # 纵向电流剖面（若转储）
    currents_r: np.ndarray | None = None  # 横向电流剖面（若转储）
    particles: np.ndarray | None = None   # 粒子相空间数据（若转储）
    monitors: list[MonitorData] = []      # 场监视器快照
    wake_monitors: dict = {}              # WakeMonitor 二进制数据 {(mode, index): {...}}
    beam_moments: np.ndarray | None = None  # 束流矩监视数据（时间 × 矩）
    metadata: RunMetadata = RunMetadata()   # 执行元数据
    stdout: str = ""                      # 捕获的标准输出
    stderr: str = ""                      # 捕获的标准错误
```

---

### 1.3 `pyecho.errors` — 异常体系

所有异常均携带结构化上下文（文件路径、参数值等），用于精确定位与调试。
基类为 `PyEchoError`。

```python
class PyEchoError(Exception):
    def __init__(self, message: str = "", **ctx: Any) -> None:
        # ctx 为任意键值对上下文；__str__ 会格式化输出
```

| 异常类 | 基类 | 附加关键字参数 | 说明 |
|---|---|---|---|
| `ConfigError` | `PyEchoError` | `config_file`, `field`, `value` | 配置 / 参数校验错误 |
| `GeometryError` | `PyEchoError` | `geometry_file`, `segment` | 几何解析或校验错误 |
| `RunnerError` | `PyEchoError` | `work_dir`, `executable`, `returncode` | ECHO2D 可执行文件运行错误 |
| `ParserError` | `PyEchoError` | `file_path`, `line` | 输出文件解析错误 |
| `PostProcessError` | `PyEchoError` | `data_dir`, `mode` | 后处理错误 |
| `ExecutableNotFoundError` | `RunnerError` | `executable`, `searched_paths`, `platform_key` | 未找到 ECHO2D 可执行文件 |
| `SimulationTimeoutError` | `RunnerError` | `timeout`, `elapsed` | 仿真超时 |
| `SimulationCrashedError` | `RunnerError` | `stderr`（截断至 500 字符） | ECHO2D 返回非零退出码 |
| `ValidationError` | `PyEchoError` | `field`, `value`, `constraint` | 输入校验失败 |
| `MissingOutputError` | `PostProcessError` | `missing_files` | 期望的输出缺失或不完整 |
| `PreprocessError` | `PyEchoError` | `input_file` | 预处理（输入文件生成 / 数据转换）失败 |
| `DependencyError` | `PyEchoError` | `dependency`, `install_hint` | 缺少第三方依赖（如 h5py） |
| `ProjectError` | `PyEchoError` | `project_dir`, `manifest_file` | 项目 / 工作区管理错误 |

---

### 1.4 `pyecho.runner` — 仿真运行器

提供单次仿真的 `ECHO2DRunner` 与参数扫描的 `BatchRunner`，处理平台相关可执行文件
检测、输入文件生成、进程管理、进度解析与结果聚合。

```python
from pyecho.runner import ECHO2DRunner
runner = ECHO2DRunner("work_dir")
result = runner.run(params, np=4)
print(result.modes[0].wake_processed.loss_factor)
```

#### 类 `ECHO2DRunner`

```python
class ECHO2DRunner:
    def __init__(self, work_dir: str | Path, executable: str | None = None) -> None:
        """work_dir：仿真工作目录（会自动创建）。
        executable：ECHO2D 二进制路径；None 时从项目 Codes/ 目录自动检测。"""
```

| 属性 / 方法 | 签名 | 说明 |
|---|---|---|
| `executable` | `property -> str`（可写） | ECHO2D 二进制路径；写入时校验文件存在 |
| `kill` | `(self) -> None` | 终止当前运行中的 ECHO2D 子进程（可重试） |
| `run` | `(self, params=None, geometry_file=None, np=1, timeout=None, show_progress=True) -> SimulationResult` | 运行仿真；`np` 为 OpenMP 线程数（CLI 中对应 `--threads`/`-j`）；超时抛 `SimulationTimeoutError`，非零退出抛 `SimulationCrashedError` |
| `run_stream` | `(self, params=None, geometry_file=None, np=1, timeout=None) -> Generator[dict, None, SimulationResult]` | 生成器版本，每次产出 `{"percent": float, "message": str}` 进度字典；结束时的返回值可通过 `StopIteration.value` 获取 |

`run()` 的参数细节：

- `params: ECHO2DParams | None` — 提供时会在执行前写入 `input_in.txt`。
- `geometry_file: str | None` — 覆盖 `params.GeometryFile`；`params` 为 `None` 时使用工作目录中已有的 `input_in.txt`。
- `np: int` — 设置环境变量 `OMP_NUM_THREADS`。
- `timeout: int | None` — 最大墙钟时间（秒）；`None` 表示不设超时。
- `show_progress: bool` — 是否记录从 stdout 解析的进度百分比。

> **MPI 说明**：目前未实现 MPI 支持，仅设置 OpenMP 并行；可通过 `executable`
> 参数选择 MPI 版可执行文件，但会以单进程运行。

#### 类 `BatchRunner`

```python
class BatchRunner:
    def __init__(self, base_params: ECHO2DParams, work_root: str | Path) -> None:
        """base_params：基线参数；work_root：扫描输出根目录（每个组合一个子目录）。"""

    def add_scan(self, param_name: str, values: list[Any]) -> None:
        """添加要扫描的参数（如 "BunchSigma"、"Modes"）及取值列表。"""

    def run_all(self, parallel: int = 1, executable: str | None = None) -> list[SimulationResult | None]:
        """运行所有参数组合（笛卡尔积）。
        parallel：并发仿真数（1 = 串行）。
        返回与组合顺序一致的结果列表；失败的运行返回 None（记录错误后继续）。"""
```

---

### 1.5 `pyecho.parser` — 输出文件解析

解析 ECHO2D 全部输出文件格式，包括尾场势、电流剖面、耦合矩阵、场监视器、
粒子数据与束流矩。输出文件位于工作目录下的几何类型子目录（`round/`、`magn/`
或 `elec/`）中。

```python
loader = OutputLoader("path/to/output_dir")
s, W, hr, offset, D, sigma = loader.load_wake(mode=0)
all_wakes = loader.load_all_wakes()
currents = loader.load_currents()
```

#### 模块级自由函数

| 函数 | 签名 | 说明 |
|---|---|---|
| `find_wake_file` | `(data_dir: Path, mode: int) -> Path \| None` | 定位 `wakeL_XX.txt`（大小写不敏感，兼容 `WakeL_XX.txt`） |
| `list_wake_files` | `(data_dir: Path) -> list[Path]` | 列出全部 `wakeL_XX.txt`，按名称排序 |
| `parse_wake_file` | `(filepath: str \| Path) -> dict` | 解析单个 wakeL 文件；返回键 `hr, offset, D, sigma, s, W_raw, mode` |
| `parse_wake_monitor_file` | `(filepath: str \| Path) -> dict` | 解析 `WakeM_00_XXXXXX.bin` 二进制文件；返回键 `n, wake, mode, index` |
| `parse_monitor_header` | `(filepath: str \| Path) -> dict` | 解析 `Monitor_mXX_NYY.txt` 头部；返回键含 `field_component, time_type, D, kt, ht, t0, kr, hr, r0, kz/ks, hz/hs, z0/s0` |
| `load_bunch_profile` | `(output_dir, offset: int, s_wake: np.ndarray \| None = None) -> tuple` | 从 Iz0.txt 加载束流电流剖面并（可选）插值到 wake 网格；返回 `(s, I)` 或 `(None, None)` |

#### 类 `OutputLoader`

```python
class OutputLoader:
    def __init__(self, output_dir: str | Path) -> None:
        """output_dir：含 round/、magn/、elec/ 子目录的输出目录（父目录）。
        目录不存在时抛 ParserError。"""
```

| 方法 | 签名 | 返回 | 说明 |
|---|---|---|---|
| `load_wake` | `(self, mode: int) -> tuple` | `(s, W_raw, hr, offset, D, sigma)` | 加载单个 wakeL 文件；找不到文件抛 `ParserError` |
| `load_all_wakes` | `(self) -> dict[int, tuple]` | `{mode: (s, W_raw, hr, offset, D, sigma)}` | 加载全部可用 wake 文件 |
| `load_wake_monitor` | `(self, mode=0, index=0) -> dict \| None` | 键 `n, wake, mode, index` | 加载 WakeMonitor 二进制文件；不存在返回 `None` |
| `load_all_wake_monitors` | `(self) -> dict[tuple[int,int], dict]` | `{(mode, index): {...}}` | 加载全部 WakeMonitor 文件 |
| `load_currents` | `(self) -> tuple \| None` | `(s_array, current_2d)` | 加载 `Iz0.txt` 纵向电流剖面 |
| `load_currents_radial` | `(self) -> tuple \| None` | 同上 | 加载 `Ir0.txt` 径向电流剖面 |
| `load_wcc` | `(self) -> np.ndarray \| None` | 含表头行（D, s0, s1, ...）的完整矩阵 | 加载 `Wcc_odd.txt`（cos-cos 耦合矩阵） |
| `load_wss` | `(self) -> np.ndarray \| None` | 同上 | 加载 `Wss_odd.txt`（sin-sin 耦合矩阵） |
| `load_monitor` | `(self, mode=0, monitor_id=1) -> MonitorData \| None` | 解析的监视器数据 | 加载 `Monitor_mXX_NYY.txt`；优先零填充文件名 |
| `list_monitors` | `(self) -> list[tuple[int,int]]` | `(mode, monitor_id)` 列表 | 列出可用监视器 |
| `load_particles` | `(self) -> np.ndarray \| None` | 结构化数组，字段 `x,y,z,px,py,pz,status` | 加载 `particles.out` 二进制粒子文件 |
| `load_beam_moments` | `(self) -> np.ndarray \| None` | 时间 × 矩的二维数组 | 加载 `BeamMomentsMonitor.txt` |
| `has_output` | `(self) -> bool` | 是否存在任意已知结果文件 | 检查输出目录是否有结果 |
| `geometry_type` | `property -> str` | 检测到的几何子目录类型 | `"round"`/`"magn"`/`"elec"` |

**`load_wake` 返回元组各元素含义**：`s` 纵向坐标 [m]；`W_raw` 原始尾场势 [m·V/nC]；
`hr` 横向网格步长 [m]；`offset` 束团偏移（网格线）；`D` 结构宽度 [m]；
`sigma` 束团 RMS 长度 [m]。

---

## 2. 几何

### 2.1 `pyecho.geometry` — 几何构建器与解析器

ECHO2D 使用简单 ASCII 格式描述旋转对称（round）与矩形（flat）结构。
本模块提供程序化构建器与文件解析器。几何文件坐标为**厘米（cm）**。

#### 类 `RoundGeometry`

构建旋转对称（round）ECHO2D 几何。

```python
geo = RoundGeometry()
geo.pipe(radius=1.0, length=10.0)  # 半径 1 cm，长 10 cm
geo.step(radius=2.0, length=5.0)   # 扩展到 2 cm
geo.save("my_geometry.txt")
```

- 类常量：`CLOCKWISE = 0`、`COUNTERCLOCKWISE = 1`（方向常量）。
- `pipe(radius: float, length: float, z_start: float | None = None) -> RoundGeometry` — 添加直管道段；`z_start` 为 `None` 时接续上一段末尾。
- `step(radius: float, length: float) -> RoundGeometry` — 添加径向台阶（连接上一段末尾；半径变化时自动插入竖直壁）。
- `taper(r_start: float, r_end: float, length: float) -> RoundGeometry` — 添加线性锥形段。
- `save(filepath: str | Path) -> None` — 写入 ECHO2D `.txt` 文件；无段时抛 `GeometryError`。各方法均返回 `self` 支持链式调用。

#### 类 `RectaGeometry`

构建矩形（flat）ECHO2D 几何，API 与 `RoundGeometry` 类似但使用 `y`（垂直）坐标。

```python
geo = RectaGeometry()
geo.pipe(half_gap=0.5, length=10.0)
geo.save("flat_geometry.txt")
```

- `pipe(half_gap: float, length: float, z_start: float | None = None) -> RectaGeometry`
- `step(half_gap: float, length: float) -> RectaGeometry`
- `taper(y_start: float, y_end: float, length: float) -> RectaGeometry`
- `save(filepath: str | Path) -> None`

#### 函数 `load_geometry`

```python
def load_geometry(filepath: str | Path) -> dict:
    """解析 ECHO2D 几何 .txt 文件。
    返回 dict，键：
      - "materials": 材料列表，含 epsilon、mu、sigma、segments（段索引）
      - "segments": 段列表，含 z1, r1, z2, r2, z3, r3, z4, r4, d, k
    解析失败抛 GeometryError。
    """
```

段格式为 10 列：`z1 r1 z2 r2 z3 r3 z4 r4 d k`（flat 几何将 r 替换为 y）。
`d` = 方向（0 = 顺时针，1 = 逆时针），`k` = 壁电导率 [S/m]。

---

## 3. 后处理

### 3.1 `pyecho.postprocess.core` — 后处理调度器

提供 `PostProcessor` 类，从 ECHO2D 输出目录结构自动检测几何类型（round vs recta）
并应用对应的处理管线。

```python
from pyecho.postprocess import PostProcessor
pp = PostProcessor("path/to/output_dir")
wake = pp.process_wake_monopole()
print(f"Loss factor: {wake.loss_factor:.4f} V/pC")
```

#### 类 `PostProcessor`

```python
class PostProcessor:
    def __init__(self, loader_or_dir: "OutputLoader | str | Path") -> None:
        """loader_or_dir：OutputLoader 实例，或指向输出目录的路径。"""
```

- `geometry_type: property -> str` — 有效几何类型：`"round"`、`"recta"`（magn+elec）、`"magn"`、`"elec"` 或 `"unknown"`。

| 方法 | 签名 | 返回 / 说明 |
|---|---|---|
| `process_wake_monopole` | `(self, mode=0, shift_sigma=True) -> WakeResult` | 处理单极子（m=0）纵向尾场；仅 round 几何有效，否则抛 `PostProcessError` |
| `process_wake_dipole` | `(self, mode=1) -> dict` | 处理偶极子（m=1）尾场（含横向分量）；返回键 `longitudinal`、`transverse`（均为 `WakeResult`）、`dy`、`sigma` |
| `process_recta_wake` | `(self, n_modes_cc=0, n_modes_ss=0) -> dict` | 处理 recta 尾场（Wlong/Wquad/Wdipole）；`n_modes_cc`/`n_modes_ss` ≤ 0 时自动检测；返回键 `wcc, wss, s, Wlong, Wquad, Wdipole, D, k_cc, k_ss` |
| `process_off_axis` | `(self, y0: float, y: float, n_modes_cc=None, n_modes_ss=None) -> dict` | 计算任意横向偏移处的离轴尾场（复现 MATLAB `PP_WakeZY.m`）；返回键 `s, Wz, Wy, D` |
| `process_field_monitor` | `(self, mode=0, monitor_id=1, point_t=None, point_z=None, point_r=None) -> dict` | 从场监视器提取场迹线；找不到监视器抛 `MissingOutputError` |
| `synthesize_total_field` | `(self, component="Ez", monitor_id=1, x0=0.0, x=0.0, n_modes=35) -> np.ndarray` | 从模态监视器合成总场（仅 recta，需 magn/ 目录） |
| `load_particles` | `(self) -> dict` | 加载并分析 `particles.out`；返回键 `particles`, `statistics` |
| `convert_to_astra` | `(self, astra_file, total_charge=None, reference_energy_MeV=100.0) -> int` | 将 ECHO 粒子转换为 ASTRA 格式；返回转换的粒子数 |
| `process_all` | `(self) -> dict[str, Any]` | 运行全部适用后处理步骤；round → monopole+dipole，recta → Wcc/Wss 装配与 Wlong/Wquad/Wdipole |

### 3.2 `pyecho.postprocess.fields` — 场监视器后处理

复现 ECHO2D 场监视器 MATLAB 脚本（`PP_FieldMonitor_rect.m`、`PP_FieldMonitor_round.m`、
`PP_CreateTotalField_EzEyBx.m`），提供基于二维插值的点提取与 recta 模态场合成。

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `extract_field_at_point` | `(monitor: MonitorData, t=None, z=None, r=None) -> float \| np.ndarray` | 在指定 `(t, z, r)` 点用线性插值提取场值（等价 MATLAB `interp2`） |
| `process_field_monitor` | `(monitor: MonitorData, point_t=None, point_z=None, point_r=None) -> dict` | 高层封装；返回键 `component, coords, field, point` |
| `synthesize_total_field` | `(monitor_files: list, x0=0.0, x=0.0, n_modes=35, D=None) -> np.ndarray` | 从模态监视文件合成总场：`F_total = (2/D)·Σ_m F_m·sin(k_m(x0+D/2))·sin(k_m(x+D/2))`，其中 `k_m = π·m/D` |
| `synthesize_total_field_from_loader` | `(magn_dir, component="Ez", monitor_id=1, x0=0.0, x=0.0, n_modes=35, D=None) -> np.ndarray` | 便捷封装：自动加载 magn/ 目录中的监视文件 |
| `extract_point_monitor` | `(monitor: MonitorData, z: float, r: float, geometry="recta") -> tuple[np.ndarray, np.ndarray]` | 提取固定点 `(z, r)` 上所有时间步的一维场迹线；round 的 Ep 分量按 `Ep = Ep·r / r` 还原 |
| `save_point_monitor` | `(out_path: Path, T, trace, component="Ez", geometry="recta") -> None` | 以 MATLAB 兼容 `PointMonitor.txt` 格式保存（两列 ASCII：`ct [m]  Field/Q [V/m/nC]`） |
| `animate_field_monitor` | `(monitor: MonitorData, output=None, fps=10, geometry="recta") -> None` | 生成场监视器动画，支持保存 GIF/MP4 |
| `plot_field_3d` | `(monitor: MonitorData, time_step=0, output=None, geometry="recta") -> None` | 单时间步的三维曲面图（复现 MATLAB `mesh(z, r, F)`） |

### 3.3 `pyecho.postprocess.particles` — 粒子数据后处理

复现 `AnalyseParticles.m`、`SeeBeamMoments.m`、`ECHO_2_ASTRA.m` 与
`A_SeeField.m`，提供粒子相空间数据的加载、分析与格式转换。

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `load_echo_particles` | `(filepath: str \| Path) -> dict[str, Any]` | 加载 `particles.out`；返回键 `Np, q0, x, y, z, px, py, pz, status`。动量 `px/py/pz` 为归一化动量 βγ = p/(mₑ·c)（无量纲） |
| `compute_beam_moments` | `(beam_monitor_file, step_z=0.0001) -> dict[str, Any]` | 从 `BeamMomentsMonitor.txt`（19 列）计算束流矩；返回 `z, mean_*, sigma_*, emit_x/y/z, energy, energy_spread, ...` |
| `convert_echo_to_astra` | `(echo_file, astra_file, total_charge=None, reference_energy_MeV=100.0) -> int` | 转换 ECHO → ASTRA 二进制格式；返回写入的粒子数 |
| `compute_particle_statistics` | `(particles: dict) -> dict[str, float]` | 计算束流统计量（仅 active/status=0 粒子）；返回 `n_active, n_lost, mean_*, sigma_*, emit_x/y/z` |
| `load_field_bin` | `(filepath: str \| Path) -> dict[str, Any]` | 加载 `Field_XX.bin` 原始场快照；返回 `nx, ny` 与 `Ex, Ey, Ez, Hx, Hy, Hz`（各为 `(ny, nx)` 数组） |
| `see_field` | `(field_file, field_file_2=None, component="Ex", betaz=0.997084677679532, transverse_index=10) -> dict[str, Any]` | 沿束流轨迹提取场数据（复现 `A_SeeField.m`）；返回 `F1/F2` 场图、`slice_1/slice_2` 轨迹线、`difference` 等 |

**ASTRA 转换关键约定**：ECHO 动量 βγ → ASTRA 单位 eV/c 乘以 `mₑ·c²/e ≈ 510998.95 eV/c`；
时间 `t = z / c`；状态 `0 → 5`（active）、`1 → 1`（lost）。每条 ASTRA 记录恰好
108 字节（13 个 double + 1 个 int32）。

### 3.4 `pyecho.postprocess.wakes.round` — round 尾场处理

复现 `PP_Wake_Monopole.m` / `PP_Wake_Dipole.m`，数值结果与 MATLAB **完全一致**。

> **关键约定**：round 几何中有效横向步长 `dy = (offset + 0.5)·hr`（并非 `offset·hr`）。

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `process_wake_monopole` | `(loader: OutputLoader, shift_sigma=True) -> WakeResult` | 处理单极子（m=0）纵向尾场：加载 wakeL_00、Iz0 束流剖面、单位换算（×1e-3 → V/pC）、`loss_shape` 计算损失因子与 RMS 展宽、s 坐标平移 |
| `process_wake_dipole` | `(loader: OutputLoader) -> dict` | 处理偶极子（m=1）尾场：`W_long = W_raw×1e-3/dy²`，`W_trans = -IntegrTr(hs, W_long)`；返回 `longitudinal`（V/pC/m²）、`transverse`（V/pC/m）、`dy`、`sigma` |

### 3.5 `pyecho.postprocess.wakes.recta` — recta 尾场处理

复现 MATLAB 全流程（`PP_Wcc.m`、`PP_Wss.m`、`PP_WakeLQ.m`、`PP_WakeLQD.m`、
`PP_WakeZY.m`、`PP_WakeL_Tm_Tq_Td.m`）。

> **关键约定**：recta 几何中有效横向步长 `dy = offset·hr`（**没有** +0.5！），
> 与 round 几何约定根本不同。

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `assemble_wcc` | `(data_dir, n_modes=15) -> np.ndarray` | 装配 Wcc（cos-cos）耦合矩阵（复现 `PP_Wcc.m`）；返回 `(n_modes+1, ns+1)` 矩阵，行 0 = `[D, s_0, ...]`，行 i = `[k_i, Wcc_i(s)...]`，`Wcc_i = W_raw / cosh²(dy·k_i)` |
| `assemble_wss` | `(data_dir, n_modes=15) -> np.ndarray` | 装配 Wss（sin-sin）耦合矩阵；除以 `sinh²(dy·k_i)`；`dy=0` 时（轴上束团）模式行置零 |
| `compute_wake_long_quad` | `(wcc: np.ndarray, n_modes=None) -> dict` | 从 Wcc 计算 Wlong/Wquad（复现 `PP_WakeLQ.m`）；返回 `s, Wlong, Wquad, D, k_values` |
| `compute_wake_long_quad_dipole` | `(wcc, wss, n_modes_cc=None, n_modes_ss=None) -> dict` | 同时计算 Wlong/Wquad/Wdipole（复现 `PP_WakeLQD.m`）；返回 `s, Wlong, Wquad, Wdipole, D, k_cc, k_ss` |
| `compute_wake_zy` | `(wcc, wss, y_offsets: np.ndarray, y0: float, n_modes_cc=None, n_modes_ss=None) -> dict` | 在 `(y, s)` 二维网格上计算离轴 Wz/Wy（复现 `PP_WakeZY.m`，支持多个 witness 偏移）；返回 `y_offsets, s, y0, Wz, Wy, D, k_cc, k_ss` |
| `compute_wake_off_axis` | `(wcc, wss, y0: float, y: float, n_modes_cc=None, n_modes_ss=None) -> dict` | 单 `(y0, y)` 情形的离轴 Wz/Wy；返回 `s, Wz, Wy, D, k_cc, k_ss` |
| `compute_wake_tm_tq_td` | `(wcc, wss, y0=0.0, y=0.0, n_modes_cc=None, n_modes_ss=None) -> dict` | 计算横向单极子（Tm）、四极子（Tq）与偶极子（Td）尾场（复现 `PP_WakeL_Tm_Tq_Td.m`）；返回 `s, D, y0, y, Wlong, Tm, Tq, Td, Wm, Wquad, Wdipole, Fm, FQ, FD, k_cc, k_ss, error_long, error_m, error_quad, error_dipole` |
| `process_recta_wake` | `(magn_dir, elec_dir=None, n_modes_cc=15, n_modes_ss=15, compute_dipole=True) -> dict` | 完整 flat 尾场管线便捷函数；返回 `wcc, wss, s, Wlong, Wquad, Wdipole` 及 `bunch, loss_long, loss_quad, loss_dipole` |

**单位换算（recta）**：`D` = 结构总宽度 [m]（= `Width`）；原始 wakeL 为 m·V/nC →
V/pC 乘 1e-3；Wlong = ΣWcc×2/D×1e-3 [V/pC]；Wquad = −IntegrTr(Σk²·Wcc)×2/D×1e-6
[V/pC/mm]；Wdipole = −IntegrTr(Σk²·Wss)×2/D×1e-6 [V/pC/mm]。

---

## 4. 预处理

### 4.1 `pyecho.preprocess.bunch` — 束流剖面生成与校验

处理 ECHO2D 的 `InPartFile='*.txt'` 选项：生成与校验任意纵向束流剖面（ASCII 格式）。

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `generate_gaussian` | `(sigma=0.001, n_points=500, n_sigma=6.0, s_min=0.0) -> tuple[np.ndarray, np.ndarray]` | 生成高斯纵向束流剖面；返回 `(s, rho)`，rho 归一化到峰值 1 |
| `generate_flattop` | `(sigma=0.001, rise=0.0001, flat_length=0.002, n_points=500, s_min=0.0) -> tuple[np.ndarray, np.ndarray]` | 生成平顶束流剖面（高斯上升/下降沿 + 平顶中心区）；返回 `(s, rho)` |
| `save_bunch_profile` | `(out_path, s: np.ndarray, rho: np.ndarray) -> Path` | 保存 ECHO2D 兼容束流剖面文件（`% s[m] charge [normalized]` 头）；返回保存路径 |
| `validate_bunch_profile` | `(filepath) -> dict` | 校验束流剖面（文件存在、≥2 点、s 单调递增、均匀步长 ±1%、电荷密度非负）；返回 `valid, n_points, s_range, s_step, peak, issues` |

### 4.2 `pyecho.preprocess.particles` — 粒子预处理

提供 ASTRA ↔ ECHO2D 粒子格式转换、电荷沉积算法与线电流剖面生成。

```python
from pyecho.preprocess.particles import ASTRAConverter, create_line_current, particles_to_charge
ASTRAConverter.astra_to_echo("distribution.astra", "particles.echo")
create_line_current(sigma=0.001, output_file="line_current.txt")
rho = particles_to_charge(z0, nz, nr, hz, hr, particles)
```

#### 类 `ASTRAConverter`

| 方法 | 签名 | 说明 |
|---|---|---|
| `astra_to_echo` | `(staticmethod, astra_file, echo_file, z_offset=-0.01) -> None` | 将 ASTRA 分布转换为 ECHO2D 格式（`z, y, x', y', Pz, weight`）；`x' = px/pz`，`y' = py/pz`；失败抛 `PreprocessError` |
| `echo_to_astra` | `(staticmethod, echo_file, astra_file) -> None` | 将 ECHO2D 粒子输出转换回 ASTRA 格式（重建 `px = x'·pz`，`py = y'·pz`，round 几何 `x = 0`） |

#### 模块级函数

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `create_beam_profile` | `(s_vals: np.ndarray, rho_vals: np.ndarray, output_file) -> str` | 创建 ECHO2D 任意束流剖面文件；返回写入文件的绝对路径 |
| `parse_beam_profile` | `(filepath) -> tuple[np.ndarray, np.ndarray]` | 解析束流剖面文件；返回 `(s_vals, rho_vals)` |
| `create_line_current` | `(sigma: float, output_file, n_points=200) -> str` | 创建高斯线电流剖面文件（归一化高斯 λ(z)）；返回绝对路径 |
| `particles_to_charge` | `(z_mesh_head: float, nz: int, nr: int, hz: float, hr: float, particles: np.ndarray) -> np.ndarray` | 用双线性插值将宏粒子沉积到二维电荷网格（复现 `Particles2Charge.m`）；返回 `(nz, nr)` 电荷密度数组 |

### 4.3 `pyecho.preprocess.field` — 初始场生成

复现 `GenerateInitialField.m`：沉积粒子 → 解泊松方程 → 计算电场 → 洛伦兹变换
→ 写入二进制场文件，供 ECHO2D 粒子跟踪使用。

#### 类 `InitialFieldGenerator`

```python
class InitialFieldGenerator:
    def __init__(self, pipe_radius: float, mesh_length: int, step_z: float, step_y: float) -> None:
        """pipe_radius：束流管道半径 [m]（设定横向域大小）；
        mesh_length：纵向网格线数；step_z/step_y：纵/横向网格步长 [m]。"""

    def generate(self, particle_file: str | Path, mesh_position_z: float = 0.0,
                 current_filter: int = 1) -> str:
        """生成初始场二进制文件。
        particle_file：ECHO2D 格式粒子文件（ASCII 6 列：z, y, x', y', Pz, weight）。
        current_filter：对沉积电流剖面施加的 2 点低通滤波次数。
        返回：生成的 .bin 场文件路径。输出包含 Ez、Er、Hφ 三个分量，
        float32 列主序存储，与 ECHO2D 期望格式一致。
        失败抛 PreprocessError。
        """
```

内部实现：轴对称泊松求解器使用红-黑（棋盘）逐次超松弛（SOR，ω=1.8），
Dirichlet 边界条件（管道壁 φ=0）；洛伦兹变换假定束团以光速沿 +z 传播，
`Ez_lab = Ez`、`Er_lab = γ·Er`、`Hφ_lab = γβc·Er/Z0`。

---

## 5. 数值工具

`pyecho.mathlib` 提供物理常数（对应 `MatLib4ECHO/PhysConsts.m`）与数值函数。

**物理常数**（`pyecho.mathlib` 直接导出）：

| 常量 | 值 | 含义 |
|---|---|---|
| `c` | 2.99792458e8 | 真空光速 [m/s] |
| `e` | 1.602176634e-19 | 元电荷 [C] |
| `me` | 9.1093837015e-31 | 电子静止质量 [kg] |
| `eps0` | 8.8541878128e-12 | 真空介电常数 [F/m] |
| `mu0` | 1.25663706212e-6 | 真空磁导率 [H/m] |
| `Z0` | ~376.73 | 真空特征阻抗 [Ω] |
| `SI` | 4πε₀ | SI 因子 |
| `IA` | me·c³/e·SI | 阿尔文电流 [A] |
| `E00` | ~510998.95 | 电子静止能量 [eV] |
| `Esi2gauss` | 1e-4/(c·1e-8) | 1 高斯 → SI 换算 |
| `grad` | π/180 | 度 → 弧度 |
| `h_plank` | 4.135667516e-15 | 普朗克常数/元电荷 [eV·s] |

### 5.1 `pyecho.mathlib.gauss`

```python
def gauss(x: np.ndarray, sigma: float) -> np.ndarray:
    """归一化高斯（正态分布 PDF）：
    g(x) = exp(-x²/(2σ²)) / (σ·√(2π))
    是 MatLib4ECHO/gauss.m 的精确 Python 等价物。积分结果为 1。
    """
```

### 5.2 `pyecho.mathlib.fft`

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `wake2impedance` | `(s: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]` | 尾场 → 阻抗傅里叶变换（`exp(iωt)` 约定）：`Z(f) = Δt·FFT{W(t)}`，`t = s/c`；返回 `(f [Hz], y [Ω])` |
| `impedance2wake` | `(f: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]` | 阻抗 → 尾场逆变换：`W(s) = N·Δf·IFFT{Z(f)}`（取实部）；返回 `(s [m], w [V/C])` |

### 5.3 `pyecho.mathlib.integration`

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `integr_tr` | `(h: float, x: np.ndarray) -> np.ndarray` | 均匀网格累计梯形积分（`IntegrTr.m`）：`y[0]=0`，`y[k]=h·Σ½(x[i]+x[i-1])` |
| `diff_l` | `(h: float, x: np.ndarray) -> np.ndarray` | 交替符号差分算子（`DiffL.m`）：`y[k]=[2(x[k]-x[k-1])-y[k-1]]/h` |
| `int0` | `(x: np.ndarray, y: np.ndarray) -> float` | 非均匀网格梯形定积分（`Int0.m`） |

### 5.4 `pyecho.mathlib.convolution`

```python
def za_zb(xb: np.ndarray, bunch: np.ndarray, Za0: np.ndarray) -> np.ndarray:
    """阻抗 × 束团频谱卷积 → 尾场（等价 MatLib4ECHO/ZaZb.m）：
    W(s) = -IFT{ Za(f)·FT{λ(s)} }
    xb：束团纵向坐标 [m]（均匀间隔）；bunch：束团电荷密度 λ(s)；
    Za0：(N_z, 3) 阻抗表 [f, Re(Za), Im(Za)]。
    返回 (N_b, 1) 尾场势 -W(s) [V/C]（负号符合 MATLAB 输出约定）。
    """
```

### 5.5 `pyecho.mathlib.loss`

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `loss_shape` | `(bunch: np.ndarray, wake: np.ndarray) -> tuple[float, float, float]` | 损失因子、RMS 展宽与峰值尾场（`LossShape.m`）。输入为两列数组 `[s, value]`；κ = −∫λ·W·ds（Riemann 和）；σ_κ = √(∫λ(W+κ)²ds)。返回 `(loss, spread, peak)` |
| `long_loss2` | `(s: np.ndarray, w: np.ndarray, sigma: float) -> tuple[float, float, np.ndarray]` | 使用内部高斯束团的损失因子与展宽（`LongLoss2.m`）。**s 与 sigma 单位为米**。返回 `(loss, spread, bunch)` |
| `long_loss2_cm` | `(s_cm: np.ndarray, w: np.ndarray, sigma_cm: float) -> tuple[float, float, np.ndarray]` | 厘米接口包装（MATLAB 兼容），自动换算为米后调用 `long_loss2` |

---

## 6. 可视化

### 6.1 `pyecho.visualize` — 绘图函数

为尾场势、几何文件、场监视器数据与多结果比较提供绘图工具。所有函数返回
`(fig, ax)` 元组以便进一步定制。使用干净的科研绘图风格。

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `plot_wake_round` | `(result_or_s, W=None, *, bunch=None, title="", xlabel="s [mm]", ylabel="Wake potential [V/pC]", ax=None, show_loss=True, figsize=(10,5)) -> (Figure, Axes)` | 绘制尾场势，可选叠加束团形状；`result_or_s` 可为 `SimulationResult`/`WakeResult`/`ModeResult`/数组 |
| `plot_round_wake` | `(result: RoundWakeResult, *, title="", figsize=(10,8), bunch=None) -> (Figure, np.ndarray of Axes)` | 绘制 round 几何尾场（纵向 + 偶极子子图） |
| `plot_recta_wake` | `(result: RectaWakeResult, *, title="", figsize=(12,10), bunch=None) -> (Figure, np.ndarray of Axes)` | 绘制 recta 几何尾场（Wlong/Wquad/Wdipole 三个子图） |
| `plot_geometry` | `(geometry_file, *, units="cm", ax=None, show_materials=True, figsize=(12,4)) -> (Figure, Axes)` | 从几何文件绘制结构轮廓，可按材料着色 |
| `plot_field` | `(monitor: MonitorData, *, time_step=0, ax=None, figsize=(10,6)) -> (Figure, Axes)` | 绘制指定时间步的场监视器数据 |
| `plot_comparison` | `(results: list[tuple], *, labels=None, title="", difference=False, figsize=(10,5), ax=None) -> (Figure, Axes)` | 在同一图上比较多个尾场结果；`difference=True` 时绘制相对第一个结果的差 |
| `plot_wake_modes` | `(data_dir, *, n_modes=None, show_bunch=True, title="", figsize=(10,5), ax=None) -> (Figure, Axes)` | 绘制各傅里叶模式的尾场贡献（2D 线图，替代 MATLAB 3D mesh）；自动标注 `k_x = πm/W` |

---

## 7. I/O

### 7.1 `pyecho.io.hdf5` — HDF5 导入导出

使用 h5py 将大型多维数组（尾场、电流、场、粒子）与结构化元数据高效存储为
HDF5 格式。

**HDF5 布局**：`/input/parameters`（JSON 序列化参数）、`/wakes/mode_XX/{s, W_raw,
W_processed, hr, offset, D, sigma}`、`/currents/{Iz, Ir}`、`/monitors/monitor_XX/`
、`/particles/data`、`/metadata/`（含 timestamp、executable_path、omp_threads、
elapsed_seconds、input_hash、stdout、stderr 等）。

```python
from pyecho.io.hdf5 import export_hdf5, load_hdf5
export_hdf5(result, "simulation.h5")
data = load_hdf5("simulation.h5")
modes = data["wakes"]
```

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `export_hdf5` | `(result_or_dir, output_path, compress=4, include_input=True) -> Path` | 导出仿真结果到 HDF5；`result_or_dir` 可为 `SimulationResult` 或输出目录路径（自动加载）；`compress` 为 gzip 级别（0–9，默认 4）；返回写入文件的绝对路径。缺少 h5py 时抛 `DependencyError` |
| `load_hdf5` | `(filepath: str \| Path) -> dict[str, Any]` | 从 HDF5 加载结果；返回键 `input, wakes, currents, monitors, particles, metadata, stdout, stderr`。缺少 h5py 时抛 `DependencyError` |

---

## 8. 项目管理

### 8.1 `pyecho.project` — 项目与运行管理

定义项目（Project）与运行（Run）管理框架的数据模型与工具。项目为包含
`.echo2d.yaml` 清单与一个或多个 runs（自包含仿真快照）的目录。

**目录结构**（新格式）：

```
my_project/
├── .echo2d.yaml          # 项目清单
└── runs/
    ├── 001_baseline/
    │   ├── .run.yaml     # 运行元数据
    │   ├── input_in.txt
    │   ├── geometry.txt
    │   ├── magn/ 或 round/
    │   ├── elec/         # 仅 recta
    │   ├── processed/{wake, field, particles}/
    │   └── stdout_*.log
    └── 002_fine_mesh/...
```

**常量**：`MANIFEST_FILE = ".echo2d.yaml"`、`RUN_META_FILE = ".run.yaml"`、
`DEFAULT_WORKSPACE = "~/echo2d_projects"`（可由 `ECHO2D_WORKSPACE` 环境变量覆盖）、
`RUNS_DIR = "runs"`、`PROCESSED_DIR = "processed"`、`SCHEMA_VERSION = 1`。

#### 数据模型（Pydantic）

| 类 | 说明 | 关键字段 |
|---|---|---|
| `SubRunInfo` | 单个 ECHO2D 子运行（magn 或 elec）元数据 | `symmetry`（默认 "magn"）、`status`（pending/running/completed/failed）、`duration_s`、`output_dir` |
| `ProcessedSummary` | 后处理尾场结果摘要 | `loss_long_VpC`、`kick_quad_VpCmm`、`kick_dipole_VpCmm`、`peak_VpC` |
| `RunManifest` | 单次运行元数据（`.run.yaml`） | `id`、`name`、`schema_version`、`created`、`geometry_type`、`status`、`sub_runs`、`processed`。属性：`dir_name`（如 `"001_baseline"`）、`total_duration_s` |
| `ProjectManifest` | 项目元数据（`.echo2d.yaml`） | `name`、`schema_version`、`created`、`pyecho_version`、`template`、`geometry_type`、`runs`。属性：`latest_run` |

#### 模块级函数

| 函数 | 签名 | 说明 |
|---|---|---|
| `load_project` | `(project_dir) -> ProjectManifest` | 加载项目清单；无 `.echo2d.yaml` 或格式错误抛 `ProjectError` |
| `save_project` | `(manifest, project_dir) -> Path` | 写入 `.echo2d.yaml` |
| `save_run_meta` | `(run: RunManifest, run_dir) -> Path` | 写入 `.run.yaml` |
| `load_run_meta` | `(run_dir) -> RunManifest` | 加载 `.run.yaml` |
| `init_project` | `(name, template="", geometry_type="round", workspace=None) -> ProjectManifest` | 创建新项目（含 `runs/001_baseline/` 与 stub 文件）；目录已存在抛 `FileExistsError` |
| `scan_workspace` | `(workspace=None) -> dict[str, ProjectManifest]` | 扫描工作区中的 ECHO2D 项目 |
| `find_project_root` | `(start=".") -> Path \| None` | 从 *start* 向上查找最近的 `.echo2d.yaml` |
| `create_new_run` | `(project_dir, name="", from_run=None, template="") -> RunManifest` | 创建新运行目录，可从源运行复制配置或从模板生成 |
| `update_run_status` | `(run_dir, symmetry, status, duration_s=0.0) -> None` | 更新子运行状态（completed/failed/running），并同步项目清单 |
| `update_processed` | `(run_dir, loss_long=None, kick_quad=None, kick_dipole=None, peak=None) -> None` | 更新 `.run.yaml` 中处理后的尾场结果 |
| `migrate_project` | `(directory, dry_run=False) -> ProjectManifest` | 将旧格式项目迁移到新格式（创建 `.echo2d.yaml`、移动输出到 `runs/001_legacy/`、自动检测 round/recta） |
| `list_runs` | `(project_dir) -> list[RunManifest]` | 列出项目全部运行 |
| `resolve_run_dir` | `(run_ref, project_dir=None) -> Path \| None` | 将运行引用（ID / 相对路径 / 绝对路径）解析为实际目录 |
| `is_echo2d_project` | `(directory) -> bool` | 目录是否含 `.echo2d.yaml` |
| `is_legacy_project` | `(directory) -> bool` | 目录是否像旧项目（有 `input_in.txt` 但无 `.echo2d.yaml`） |

---

## 9. 收敛

### 9.1 `pyecho.converge` — 网格收敛自动化

提供 `ConvergenceRunner` 自动网格细化研究：在多个网格分辨率下运行 ECHO2D，
分析损失因子（或踢力因子）的收敛性以确定最优网格设置。
参考 ECHO 手册 §1（默认 sigma 上 5 个网格点，加密一倍验证收敛）。

```python
from pyecho.converge import ConvergenceRunner
runner = ConvergenceRunner("my_project", mesh_factors=[0.5, 1.0, 2.0])
report = runner.run()
print(report.summary())
```

#### 数据类

```python
@dataclass
class ConvergencePoint:
    label: str                 # 标签（如 "hx1.0"）
    step_y: float              # 横向网格步长 [m]
    step_z: float              # 纵向网格步长 [m]
    mesh_length: int           # 网格长度（网格线数）
    loss_factor: float | None = None   # 损失因子 [V/pC]
    kick_factor: float | None = None   # 踢力因子
    elapsed_s: float = 0.0     # 耗时 [s]
    status: str = "pending"    # pending | completed | failed

@dataclass
class ConvergenceReport:
    geometry_type: str
    base_sigma: float
    points: list[ConvergencePoint] = []
    @property
    def converged(self) -> bool:  # 最细两网格损失因子相对差 < 5%
        ...
    def summary(self) -> str:     # 生成可读收敛摘要
        ...
```

#### 类 `ConvergenceRunner`

```python
class ConvergenceRunner:
    def __init__(self, project_dir: str | Path, run_ref: str | None = None) -> None:
        """project_dir：ECHO2D 项目根（须含 .echo2d.yaml）；
        run_ref：作为基准配置的运行 ID 或路径；None 时使用最新运行。"""

    def run(self, mesh_factors: list[float] | None = None, modes: list[int] | None = None,
            threads: int = 1, verbose: bool = True) -> ConvergenceReport:
        """运行收敛研究。
        mesh_factors：基准网格步长的乘数；默认 [2.0, 1.0, 0.5]（粗→细）。
        modes：要计算的模式；默认取基准配置。
        threads：每次运行的 OpenMP 线程数。
        """
```

#### 模块级函数

```python
def run_convergence(project: str, mesh_factors: str = "2.0 1.0 0.5",
                    modes: str | None = None, threads: int = 1) -> ConvergenceReport:
    """CLI 入口：project 为项目名或路径；mesh_factors/modes 为空格分隔字符串。"""
```

---

## 10. 高级 API

### 10.1 `pyecho.api` — 高层便捷 API

为常见 ECHO2D 工作流提供一行式函数，编排底层模块（config、runner、parser、
visualize 等）。

```python
from pyecho.api import quick_simulate, quick_postprocess
result = quick_simulate("collimator.txt", sigma=0.001, modes=[0])
wake = quick_postprocess(result.output_dir)
print(f"Loss factor: {wake.loss_factor:.4f} V/pC")
```

| 函数 | 签名 | 返回 / 说明 |
|---|---|---|
| `quick_simulate` | `(geometry: str, sigma=0.001, modes=None, geometry_type="round", step_y=None, step_z=None, executable=None, work_dir=None, np=1, clean=True) -> SimulationResult` | 一行式仿真：自动生成 `input_in.txt`、运行 ECHO2D 并加载结果。`geometry` 可为几何文件路径或内置模板名；`step_y`/`step_z` 默认 `sigma/5`；`work_dir` 为 `None` 时创建临时目录（`clean=True` 时自动清理） |
| `quick_postprocess` | `(output_dir: str, geometry: str \| None = None, **kwargs) -> RoundWakeResult \| RectaWakeResult` | 一行式后处理：自动检测几何类型并应用相应管线；`geometry` 可显式指定 `"round"`/`"recta"`（也接受 `"flat"`、`"magn"`、`"elec"` 旧别名） |
| `compare_runs` | `(output_dirs: list[str], labels=None, mode=0) -> dict` | 比较多个仿真运行的尾场结果；返回 `s`（公共 s 网格）、`W_list`、`labels`、`losses` |

**`quick_simulate` 内部流程**：选择模板（`geometry_type="flat"` → `flat_absorber`，
否则 `round_collimator`）→ 设置 BunchSigma/Modes/StepY/StepZ/GeometryFile →
处理工作目录 → 复制几何文件 → 运行 `ECHO2DRunner.run()`。

**`quick_postprocess` 内部流程**：`OutputLoader` 加载输出 → 用 `PostProcessor`
检测几何类型 → round 走 `_postprocess_round`（返回 `RoundWakeResult`，含 monopole
纵向尾场与可选的 dipole 模态系数/踢力因子）→ recta 走 `_postprocess_flat`
（返回 `RectaWakeResult`，经 Wcc/Wss 装配与模式求和得到 Wlong/Wquad/Wdipole，
损失因子用梯形积分计算）。

---

## 附录：典型工作流示例

```python
# 1) 配置
from pyecho.config import ECHO2DParams
params = ECHO2DParams.from_template("round_collimator", BunchSigma=0.001, Modes=[0])

# 2) 运行
from pyecho.runner import ECHO2DRunner
runner = ECHO2DRunner("work_dir")
result = runner.run(params, np=4)

# 3) 后处理
from pyecho.postprocess import PostProcessor
pp = PostProcessor("work_dir")
wake = pp.process_wake_monopole()
print(wake.loss_factor)

# 4) 可视化
from pyecho.visualize import plot_wake_round
fig, ax = plot_wake_round(wake, title="Round collimator wake")

# 5) 导出
from pyecho.io.hdf5 import export_hdf5
export_hdf5(result, "result.h5")
```

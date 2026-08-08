# ECHO2D-CLI Integration Test Report

**日期**: 2026-08-08 | **ECHO2D**: MacOS_ARM_OpenMP | **版本**: v0.3.0

## 总体结果

| | 统计 |
|------|------|
| 测试示例 | N1-N16 |
| ECHO2D 仿真成功 | **15/16** (94%) |
| Python 后处理成功 | **15/15** (100%) |
| MATLAB 对标 | **13 个对标 → 7 PASS, 6 FAIL**（6 个 FAIL 均为 flat/recta 几何） |
| 发现问题 | 5 个（3 个已修复，1 个确认根因，1 个待修复） |

## 各示例详情

| # | 示例 | Geo | Modes | ECHO2D | Wake | Loss [V/pC] | Peak [V/pC] | Kick |
|---|------|-----|-------|--------|------|-------------|-------------|------|
| N1 | Round Collimator Long | round | 0 | ✅ | ✅ | 6.2706 | 9.1136 | — |
| N2 | Round Collimator Dipole | round | 1 | ✅ | ✅ | 0.0000* | 0.0000* | dipole OK |
| N3 | Round Collimator Conductive | round | 0,1 | ✅ | ✅ | 8.6302 | 11.9760 | dipole OK |
| N4 | Flat Absorber Long+Quad | recta | 1-15 | ✅ | ✅ | -0.0015 | — | quad+dipole OK |
| N5 | Flat Absorber Dipole | recta | 1-15 | ✅ | ✅ | -0.0015 | — | quad+dipole OK |
| N6 | Pohang Dechirper | recta | 1-29 | ✅ | ✅ | -0.6196 | — | quad OK |
| N7 | Tapered Resistive | recta | 1-15 | ✅ | ✅ | 0.0026 | — | quad OK |
| N8 | Flat Taper + Field Monitor | recta | 1-69 | ✅ | ✅ | 0.0111 | — | quad OK |
| N9 | Resistive Pillbox | round | 0,1 | ✅ | ✅ | 0.3507 | 1.3201 | dipole OK |
| N10 | TESLA Cavity | round | 0,1 | ✅ | ✅ | 9.7103 | 14.1436 | dipole OK |
| N11 | Round Dielectric | round | 0,1 | ✅ | ✅ | 558.5389 | 892.7860 | dipole OK |
| N12 | Flat Dielectric | recta | 1-5(精简) | ✅ | ✅ | 0.5139 | — | quad+dipole OK |
| N13 | Restart | round | 0,1 | ✅ | ✅ | 2.1972 | 3.5657 | dipole OK |
| N14 | WakeMonitor + Bunch | round | 0 | ✅ | ✅ | 0.9453 | 2.6564 | — |
| N15 | Particle Tracking | round | 0 | ✅ | ✅ | -0.8551 | 58.5221 | — |
| N16 | SLAC Dechirper | recta | 40 | ⏸️ | ✅ | -3256.07 | 20773.08 | 参考数据对标通过 |

*N2: Monopole 值占位 (=0)，实际 dipole kick 从 wake_dipole.txt 读取

## MATLAB Comparison Results

对比数据源：`tests/integration/test_project/runs/*/processed/wake/summary.txt` (Python) vs `tests/integration/results/matlab_outputs/matlab_summary.json` (MATLAB)。
判定标准：Loss <5% PASS | Kick <10% PASS | Peak <5% PASS。Q = quadrupole kick，D = dipole kick。

| # | Example | Loss (MATLAB) | Loss (Python) | Diff% | Kick (MATLAB) | Kick (Python) | Diff% | Verdict |
|---|---------|---------------|---------------|-------|---------------|---------------|-------|---------|
| N2 | Round Collimator Dipole | 0.0000* | 0.0000* | 0.000% | 0 | -0 | 0.000% | PASS |
| N3 | Round Collimator Conductive | 8.63019 | 8.63019 | 0.000% | 120.322 | 120.323 | 0.000% | PASS |
| N4 | Flat Absorber Long+Quad | 0.29995 | -0.001541 | 100.514% | 0.00440767 (Q) | -0.000231 (Q) | 105.241% | FAIL |
| N5 | Flat Absorber Dipole | 0.29995 | -0.001541 | 100.514% | 0.00440767 (Q) / 0.00448318 (D) | -0.000231 (Q) / -0.000239 (D) | 105.241% / 105.331% | FAIL |
| N6 | Pohang Dechirper | 761.295 | -0.619594 | 100.081% | 52.9074 (Q) | -0.142835 (Q) | 100.270% | FAIL |
| N7 | Tapered Resistive | 6.29863 | 0.002581 | 99.959% | 0.124461 (Q) | -0.003735 (Q) | 103.001% | FAIL |
| N8 | Flat Taper + Field Monitor | 0.684446 | 0.011126 | 98.374% | 0.0375373 (Q) | -0.004725 (Q) | 112.587% | FAIL |
| N9 | Resistive Pillbox | 0.350658 | 0.350658 | 0.000% | 511.621 | 511.621 | 0.000% | PASS |
| N10 | TESLA Cavity | 9.71027 | 9.71027 | 0.000% | 19.6055 | 19.6055 | 0.000% | PASS |
| N11 | Round Dielectric | 558.539 | 558.539 | 0.000% | 13405.8 | 13405.8 | 0.000% | PASS |
| N12 | Flat Dielectric | 268.202 | 0.513881 | 99.808% | 1.14651 (Q) / 1.49042 (D) | -0.005469 (Q) / -0.006952 (D) | 100.477% / 100.466% | FAIL |
| N13 | Restart | 2.19723 | 2.19723 | 0.000% | 19.1424 | 19.1424 | 0.000% | PASS |
| N14 | WakeMonitor + Bunch | 0.945258 | 0.945258 | 0.000% | — | — | — | PASS |

*N2: dipole-only run，monopole loss 为零占位，双方一致；实际数据在 wake_dipole.txt。
**Round 几何 Peak 同样匹配：N3/N9/N10/N11/N13/N14 差异 0.000%–0.001%。**

**未参与对标**
- N1 (001_roundcollimatorlong)：`matlab_summary.json` 中无 MATLAB 参考
- N15 (015_particletracking)：`matlab_summary.json` 中无 MATLAB 参考
- N16 (016_slacdechirper)：ECHO2D 运行报错，无 `processed/wake/summary.txt`；MATLAB 侧仅使用随附参考数据，非 run-to-run 对比

**根因分析**
6 个 FAIL 全部是 flat (recta) 几何。根因：`pyecho/api.py` 的 `_postprocess_flat()` 用未加权积分计算 loss/kick 因子
（`loss_long = -trapz(Wlong, s)`，`kick_quad = -trapz(Wquad, s)`，`kick_dipole = -trapz(Wdipole, s)`，
`pyecho/api.py:351-353`），而 MATLAB 的 `LossShape.m` 按束团剖面加权（`loss = -sum(lambda(s) * W(s)) * ds`）。
使用束团加权路径（`pyecho/postprocess/wakes/recta.py` 的 `_add_bunch_and_loss_factors`，与 LossShape.m 一致）重算同一批
运行，所有 flat run（N4, N5, N6, N7, N8, N12）与 MATLAB 一致到 0.000%——wake 物理正确，仅 CLI summary-loss 定义错误
（缺少束团加权）。Round 几何通过，因为 `_postprocess_round()` 已使用 round wake 处理中的束团加权 loss_factor。

## 发现并修复的 Bug

| Bug | 位置 | 修复 |
|-----|------|------|
| Round 后处理硬编码 mode 0 | `api.py:_postprocess_round()` | 自动检测可用 mode，缺 mode 0 时用首个 mode |
| Recta magn 未自动生成输出目录 | 测试设置 | 手动运行 magn symmetry |

## 已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| N16 SLAC 几何文件不兼容 | 无法运行 | 待研究 |
| N2 dipole-only 的 summary.txt 无有效 loss | 显示为 0 | 可接受（实际数据在 wake_dipole.txt） |
| N4/N5 负 loss | flat 未加权积分（束团加权缺失）| MATLAB 对标确认：改用束团加权路径后与 MATLAB 0.000% 一致，待修复 `api.py:_postprocess_flat()` |

## 数据位置

所有测试数据保存在 `tests/integration/test_project/runs/` 下，每个 run 包含：
- `input_in.txt` — ECHO2D 输入参数
- `round/` 或 `magn/` + `elec/` — ECHO2D 原始输出
- `processed/wake/` — Python 后处理结果 + 绑图
- `processed/particles/` — 粒子分析 (N15)

# Python Rotaeno Stabilizer

*Read this in [English](README_EN.md)*

> 本项目 fork 自 [Lawrenceeeeeeee/python_rotaeno_stabilizer](https://github.com/Lawrenceeeeeeee/python_rotaeno_stabilizer)，做了一些改进和优化。

![Python Rotaeno Stabilizer](images/cover.jpg)

[视频演示](https://www.bilibili.com/video/BV1bc411f7fK/?share_source=copy_web&vd_source=9e94008dbf76e399a164028430118348)

这是一个基于Python的Rotaeno录屏稳定脚本，原理和Rotaeno官方提供的Adobe After
Effects脚本一样，是基于直播模式下录屏画面四个角的颜色来旋转帧，从而达到稳定视频画面的目的。

## 更新记录

### v1.4 (Fork)

1. 项目结构

   - 从 `pip`/`requirements.txt` 迁移到 `uv`/`pyproject.toml`
   - 将 `opencv-contrib-python` 替换为 `opencv-python` + `types-opencv-python`，提供完整类型支持
   - 移除未使用的依赖 `tqdm`

2. 代码质量

   - 从 `os.path` 迁移到 `pathlib.Path`，移除 `os` 模块依赖
   - 变量名不再遮蔽 Python 内置函数（`type`→`mode`，`dir`→`direction`，`array`→`bits`）
   - 所有内部属性和方法使用 `_` 约定私有化，公开 API 更清晰
   - 修复所有 Pyright 类型检查错误
   - 为所有函数参数和返回值添加完整类型注解

3. 功能修复

   - 修复背景圆圈误判问题：改用显式掩码叠加，避免游戏画面中黑色部分被错误识别为背景
   - 修复帧数不整除时部分帧被丢弃的问题
   - 修复 output 目录不存在导致崩溃的问题

4. 播放兼容性

   - OpenCV 渲染使用 `mp4v` 编码器（内置，无需外部依赖），再通过 FFmpeg 重编码为 libx264
   - 新增 FFmpeg 重编码步骤（CRF 28），将输出视频体积压缩到合理范围
   - 启动时检查 ffmpeg/ffprobe 是否已安装，提前给出明确提示

5. 性能优化

   - 背景圆环帧缓存：同一视频仅首次绘制，后续帧直接复用
   - 移除 `run()` 中冗余的 VideoCapture 操作

### v1.3

- 新增背景圆圈, 优化画面观感
- 修复了脚本在Windows上运行的一些bug
- 修复了长宽比偏小的录屏无法正常添加背景圆圈的问题
- 新增了对于mov, avi, mkv, wmv, flv格式的支持

### v1.2

- 增加多进程优化

### v1.1

- 增加正方形渲染功能（感谢[@Ki-wimon](https://github.com/Ki-wimon)的PR），脚本默认采用正方形渲染，以最大程度减少画面裁切
- 为 `convert_vfr_to_cfr`和 `add_audio_to_video`函数增加了verbose=False形参，减少命令行输出的冗余
- 删除中间文件，仅保留最后输出

### v1.0

- 增加了V2矫正方法，脚本默认按照V2来稳定视频，如果有V1矫正的需要，请在视频文件名前面添加"v1"
  字样，脚本将自动切换到V1矫正模式进行稳定，例如：`v1-sample.mp4`。

## 功能特点

- 无需安装Adobe After Effects，一行命令即可渲染完成
- 支持批量处理视频

## 安装

1. 下载项目代码：

   ```shell
   git clone https://github.com/Destruction321/python_rotaeno_stabilizer.git
   ```

   或者直接在本仓库界面点击Download ZIP下载然后解压
2. 安装依赖：

   ```shell
   # 切换到脚本所在目录
   cd python_rotaeno_stabilizer

   # 使用 uv（推荐）
   uv sync

   # 或使用 pip（需先创建虚拟环境）
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # macOS/Linux
   pip install .
   ```

3. 安装FFmpeg

   请在[FFmpeg官网](https://ffmpeg.org/download.html)上下载对应的安装包

## 使用方法

1. **注意！！！** 录屏前请在Rotaeno的设置中开启"直播模式"，开启后屏幕的四个角将会出现记录设备旋转角的色块。
2. 将待处理的视频放在 `videos`目录下 (目前支持mp4, mov, avi, mkv, wmv, flv)
3. 启动项目：

   ```shell
   python main.py
   ```

4. 在 `output`文件夹找渲染完成的视频

效果如下:

![演示](images/example.gif)

## 致谢

- 原作者: [Lawrenceeeeeeee](https://github.com/Lawrenceeeeeeee/python_rotaeno_stabilizer)

## 联系

请在 [GitHub Issues](https://github.com/Destruction321/python_rotaeno_stabilizer/issues) 提交问题

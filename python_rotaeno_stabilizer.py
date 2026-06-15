from functools import wraps
from math import ceil, sqrt
from multiprocessing import Pool, Manager, cpu_count
from pathlib import Path
from subprocess import run, PIPE, STDOUT, DEVNULL
from time import time, sleep, strftime, gmtime

import cv2
from numpy import zeros, array
from numpy.linalg import norm
import shutil


def _timer(fn):
    """计算性能的修饰器"""
    @wraps(fn)
    def measure_time(*args, **kwargs):
        t1 = time()
        result = fn(*args, **kwargs)
        t2 = time()
        print(f"@timer: {fn.__name__} took {t2 - t1: .5f} s")
        return result

    return measure_time


class RotaenoStabilizer:
    format_to_fourcc = {
        '.mp4': 'mp4v',
        '.mov': 'mp4v',
        '.avi': 'XVID',  # 或 'DIVX'
        '.mkv': 'mp4v',
        '.wmv': 'WMV1',
        '.flv': 'FLV1'
    }

    def __init__(self, video, mode="v2", square=True):
        self._mode = mode
        self._square = square

        video_path = Path(video)
        self._video_dir = str(
            video_path
            if video_path.is_absolute()
            else Path.cwd() / 'videos' / video
        )  # 判断是否为绝对路径

        self._video_file_name = video_path.name  # 获取不带路径的文件名
        self._video_name = video_path.stem  # 获取文件名
        self._video_extension = video_path.suffix  # 获取文件后缀

        output_dir = Path.cwd() / 'output'
        output_dir.mkdir(exist_ok=True)
        self._output_path = str(output_dir / f'{self._video_name}_stb{self._video_extension}')  # 指定输出路径

        self._cfr_output_path = str(output_dir / f'{self._video_name}_cfr{self._video_extension}')  # 指定输出路径

        cap = cv2.VideoCapture(self._video_dir)
        self._fps = cap.get(cv2.CAP_PROP_FPS)

        if self._video_extension.lower() in self.format_to_fourcc:
            self._fourcc = cv2.VideoWriter.fourcc(*self.format_to_fourcc[self._video_extension.lower()])
        else:
            raise ValueError(f"Unsupported video format: {self._video_extension}")
        
        cap.release()

        self._num_cores = min(cpu_count() or 1, 61)

    @_timer
    def _add_audio_to_video(self, input_video=None, audio=None, verbose=True):
        """
        将音频添加到视频中。

        :param input_video: 输入的视频文件路径。如果为 None，则使用实例的 output_path 属性。
        :param audio: 输入的音频来源文件路径。如果为 None，则使用实例的 video_dir 属性。
        :param verbose: 是否显示详细的 ffmpeg 输出，默认为 False。
        :return: None
        """
        if input_video is None:
            input_video = self._output_path
        if audio is None:
            audio = self._video_dir
        output_file = f'output/{self._video_name}{self._video_extension.lower()}'
        command = [
            'ffmpeg',
            '-i', input_video,  # 输入的视频文件
            '-i', audio,  # 输入的音频来源文件
            '-c:v', 'copy',  # 复制视频流
            '-c:a', 'aac',  # 使用 AAC 编码音频
            '-strict', 'experimental',
            output_file  # 输出的文件名
        ]

        if not verbose:
            # 抑制 stdout 和 stderr 输出
            run(command, stdout=DEVNULL, stderr=DEVNULL)
        else:
            run(command)

    @_timer
    def _convert_vfr_to_cfr(self, verbose=True):
        """
        将可变帧率 (VFR) 视频转换为固定帧率 (CFR) 视频。

        :param verbose: 是否显示详细的 ffmpeg 输出，默认为 False。
        :return: None
        """
        cmd = [
            'ffmpeg',
            '-i', self._video_dir,
            '-vf', f'fps={self._fps}',
            '-c:a', 'copy',  # 复制音频流而不重新编码
            self._cfr_output_path
        ]
        if not verbose:
            # 抑制 stdout 和 stderr 输出
            run(cmd, stdout=DEVNULL, stderr=DEVNULL)
        else:
            run(cmd)

    def _get_video_duration(self, video_path):
        """
        :param video_path: 视频路径
        :return: 时长
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]

        result = run(cmd, stdout=PIPE, stderr=STDOUT)
        return float(result.stdout)

    def _compute_rotation(self, left_color, right_color, center_color, sample_color):
        """
        根据画面四个角的颜色来计算画面旋转角度
        
        :param left_color:
        :param right_color:
        :param center_color:
        :param sample_color:
        :return: 旋转角度
        """
        OffsetDegree = 180.0

        centerDist = norm(array(center_color) - array(sample_color))
        leftLength = norm(array(left_color) - array(center_color))
        leftDist = norm(array(left_color) - array(sample_color))
        rightDist = norm(array(right_color) - array(sample_color))

        direction = -1 if leftDist < rightDist else 1
        if leftLength == 0:
            angle = OffsetDegree  # 或其他合适的默认值
        else:
            angle = (centerDist - leftLength) / leftLength * 180.0 * direction + OffsetDegree

        # 注意，如果旋转方向是相反的，只需返回-angle即可
        return -angle

    def _compute_rotation_v2(self, top_left_color, top_right_color, bottom_left_color, bottom_right_color):
        '''
        根据画面四个角的颜色来计算画面旋转角度
        
        :param top_left_color: 左上角的颜色 (RGB)
        :param top_right_color: 右上角的颜色 (RGB)
        :param bottom_left_color: 左下角的颜色 (RGB)
        :param bottom_right_color: 右下角的颜色 (RGB)
        :return: 旋转角度
        '''

        # 将RGB值转换为0或1
        def convert_color_to_binary(color):
            bits = [1 if c >= 255 / 2 else 0 for c in color]
            return bits[::-1]  # OpenCV的BGR顺序和RGB相反

        # 将四个角的颜色转换为二进制
        binary_top_left = convert_color_to_binary(top_left_color)
        binary_top_right = convert_color_to_binary(top_right_color)
        binary_bottom_left = convert_color_to_binary(bottom_left_color)
        binary_bottom_right = convert_color_to_binary(bottom_right_color)

        # 将二进制颜色值转换为角度
        color_to_degree = (
            binary_top_left[0] * 2048 + binary_top_left[1] * 1024 + binary_top_left[2] * 512
            + binary_top_right[0] * 256 + binary_top_right[1] * 128 + binary_top_right[2] * 64
            + binary_bottom_left[0] * 32 + binary_bottom_left[1] * 16 + binary_bottom_left[2] * 8
            + binary_bottom_right[0] * 4 + binary_bottom_right[1] * 2 + binary_bottom_right[2]
        )
        rotation_degree = color_to_degree / 4096 * -360

        return -rotation_degree

    def _reencode_output(self, crf=28, preset='medium', verbose=True):
        """
        使用 FFmpeg 重编码拼接后的视频以控制码率。

        OpenCV VideoWriter 不提供码率控制，H264 编码器默认近无损导致文件膨胀。
        此方法用 CRF 重编码，将体积压缩到合理范围。

        参数:
        - crf: CRF 值 (0–51)，越小画质越高体积越大，默认 28。
        - preset: 编码器预设 (ultrafast/fast/medium/slow)，默认 medium。
        - verbose: 是否显示详细的 ffmpeg 输出，默认为 True。
        """
        temp_path = str(Path(self._output_path).with_stem(Path(self._output_path).stem + '_temp'))
        command = [
            'ffmpeg',
            '-i', self._output_path,  # 输入：拼接好的稳定视频（无音频）
            '-c:v', 'libx264',
            '-crf', str(crf),
            '-preset', preset,
            '-tune', 'fastdecode',
            '-an',  # 输入没有音频，显式忽略
            temp_path,
        ]

        if verbose:
            run(command, check=True)
        else:
            run(command, stdout=DEVNULL, stderr=DEVNULL, check=True)

        # 用重编码后的文件替换原文件
        Path(self._output_path).unlink()
        Path(temp_path).rename(self._output_path)

        if verbose:
            print(f"视频重编码完成 (CRF {crf})")

    def _get_background_frame(self, height, width, max_size):
        """缓存并返回带白色圆环的背景帧，避免每帧重建。"""
        key = (height, width)
        if not hasattr(self, '_bg_cache') or self._bg_cache[0] != key:
            bg = zeros((max_size, max_size, 3), dtype='uint8')
            real_height = height if width / height >= 1.7763157895 else width / 1.7763157895
            center = (max_size // 2, max_size // 2)
            radius = (1.5574 * real_height) // 2
            thickness = int(3 / 328 * real_height - 46 / 41)
            cv2.circle(bg, center, ceil(radius), (255, 255, 255), thickness=thickness)
            self._bg_cache = (key, bg)
        
        return self._bg_cache[1]

    def _process_frame(self, frame):
        height, width, _ = frame.shape

        # Sample colors from the four corners
        O = 5
        S = 3
        bottom_left = frame[height - O:height - O + S, O:O + S].mean(axis=(0, 1))
        top_left = frame[O:O + S, O:O + S].mean(axis=(0, 1))
        bottom_right = frame[height - O:height - O + S, width - O:width - O + S].mean(axis=(0, 1))
        top_right = frame[O:O + S, width - O:width - O + S].mean(axis=(0, 1))

        if self._mode == 'v2':
            angle = self._compute_rotation_v2(top_left, top_right, bottom_left, bottom_right)
        else:
            angle = self._compute_rotation(top_left, bottom_right, top_right, bottom_left)

        # Rotate frame
        max_size = ceil(sqrt(width ** 2 + height ** 2))
        if not self._square:
            M = cv2.getRotationMatrix2D((width / 2, height / 2), float(angle), 1)
            return cv2.warpAffine(frame, M, (width, height))
        
        # 使用缓存的白色圆环背景，避免每帧重建
        background_frame = self._get_background_frame(height, width, max_size)

        # 将原始视频帧放置在中间
        expanded_frame = zeros((max_size, max_size, 3), dtype='uint8')
        x_offset = (max_size - width) // 2
        y_offset = (max_size - height) // 2
        expanded_frame[y_offset:y_offset + height, x_offset:x_offset + width] = frame

        # 对扩展帧进行旋转
        M = cv2.getRotationMatrix2D((max_size // 2, max_size // 2), float(angle), 1)
        rotated_frame = cv2.warpAffine(expanded_frame, M, (max_size, max_size))
        
        # 创建一个与原扩展帧相同大小的掩码，只标记原始视频帧区域，初始为全0
        mask = zeros((max_size, max_size), dtype='uint8')
        # 在掩码上标记原始视频帧的位置
        mask[y_offset:y_offset + height, x_offset:x_offset + width] = 255
        
        # 旋转掩码（与扩展帧相同的变换）
        rotated_mask = cv2.warpAffine(mask, M, (max_size, max_size))
        
        # 使用掩码将旋转后的视频帧叠加到背景上，只覆盖旋转后的视频帧区域，其他区域显示背景圆环
        rotated_frame_masked = cv2.bitwise_and(rotated_frame, rotated_frame, mask=rotated_mask)
        background_masked = cv2.bitwise_and(
            background_frame, background_frame, 
            mask=cv2.bitwise_not(rotated_mask)
        )        
        return cv2.add(background_masked, rotated_frame_masked)

    def _process_video(self, group_number, start_position, frame_count, progress_dict):
        cap = cv2.VideoCapture(self._cfr_output_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_position)
        proc_frames = 0
        inter_output_path = str(
            Path.cwd() / 'output' / "{}.{}".format(group_number, f'{self._video_extension.lower()[1:]}')
        )

        frame_size = ceil(sqrt(int(cap.get(3)) ** 2 + int(cap.get(4)) ** 2))
        if self._square:  # 方形
            out = cv2.VideoWriter(inter_output_path, self._fourcc, self._fps, (frame_size, frame_size))
        else:
            out = cv2.VideoWriter(inter_output_path, self._fourcc, self._fps, (int(cap.get(3)), int(cap.get(4))))

        update_interval = max(1, frame_count // 100)  # 每1%更新一次

        while proc_frames < frame_count:
            ret, frame = cap.read()
            if ret:
                out.write(self._process_frame(frame))
            else:
                print("Error reading frame")
            proc_frames += 1

            # 定期更新进度
            if proc_frames % update_interval == 0:
                progress_dict[group_number] = proc_frames

        # 最终更新
        progress_dict[group_number] = frame_count
            
        cap.release()
        out.release()
        return None

    def _concatenate_videos(self, verbose=True):
        # 构建 FFmpeg 命令
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',  # 如果文件名包含特殊字符，需要此选项
            '-i', 'output/intermediate_files.txt',
            '-c', 'copy',  # 使用 'copy' 来避免重新编码
            self._output_path
        ]

        # 执行命令
        if not verbose:
            # 抑制 stdout 和 stderr 输出
            run(cmd, stdout=DEVNULL, stderr=DEVNULL)
        else:
            run(cmd)

    @_timer
    def _render(self):
        """
        :return: 无返回值：
        在output文件夹中输出渲染完毕的视频
        """
        cap2 = cv2.VideoCapture(self._cfr_output_path)
        total_frames = int(cap2.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        base_jump = total_frames // self._num_cores  # 每个进程基准帧数
        remainder = total_frames % self._num_cores  # 余数帧均匀分配到前几个进程
        fps = cap2.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        cap2.release()

        print(f"开始渲染: {total_frames}帧, {fps:.2f}fps, 时长: {duration:.2f}秒")
        print(f"使用 {self._num_cores} 个核心 ({base_jump}帧/核 + {remainder}帧余数)")

        start_time = time()

        # 分配每组的帧数（余数均匀分布到前几个进程）
        group_counts = [base_jump] * self._num_cores
        for i in range(remainder):
            group_counts[i] += 1

        # 计算每组的起始位置（累计偏移）
        group_starts = []
        cumulative = 0
        for count in group_counts:
            group_starts.append(cumulative)
            cumulative += count

        # 使用manager创建共享变量来追踪进度
        manager = Manager()
        progress_dict = manager.dict()
        for i in range(self._num_cores):
            progress_dict[i] = 0

        # 启动进程池
        p = Pool(self._num_cores)
        video_list = [(i, group_starts[i], group_counts[i], progress_dict) for i in range(self._num_cores)]
        result = p.starmap_async(self._process_video, video_list)
        
        # 显示FFmpeg风格的进度
        last_update = time()
        last_frame = 0
        
        while not result.ready():
            sleep(0.5)  # 每0.5秒更新一次
            
            current_time = time()
            elapsed = current_time - start_time
            
            # 计算总进度
            total_processed = sum(progress_dict.values())
            
            if total_processed <= last_frame and current_time - last_update < 1:
                continue

            # 计算帧率
            if elapsed > 0:
                current_fps = total_processed / elapsed
            else:
                current_fps = 0
               
            # 计算预计剩余时间
            if total_processed > 0 and current_fps > 0:
                remaining_frames = total_frames - total_processed
                eta = remaining_frames / current_fps
                eta_str = strftime("%H:%M:%S", gmtime(eta))
            else:
                eta_str = "N/A"
                
            # 计算进度百分比
            percent = (total_processed / total_frames) * 100 if total_frames > 0 else 0
                
            # 计算已处理时间
            processed_time = total_processed / fps if fps > 0 else 0
            
            # FFmpeg风格输出
            print(
                f"\rframe={total_processed:6d} fps={current_fps:4.1f} progress={percent:5.1f}% "
                f"time={processed_time:02.0f}:{processed_time%60:04.1f} "
                f"bitrate=N/A speed={current_fps/fps if fps>0 else 0:.3f}x "
                f"eta={eta_str}", end="", flush=True
            )
                
            last_update = current_time
            last_frame = total_processed
        
        # 完成
        total_time = time() - start_time
        print(f"\r渲染完成! 总用时: {total_time:.2f}秒, 平均帧率: {total_frames/total_time:.2f}fps")
        
        p.close()
        p.join()
        
        print("正在拼接视频片段...")
        
        intermediate_files = ["{}.{}".format(i, f'{self._video_extension.lower()[1:]}') for i in range(self._num_cores)]
        
        with open("output/intermediate_files.txt", "w") as f:
            for t in intermediate_files:
                f.write("file {} \n".format(t))

        self._concatenate_videos()

        # 删除中间文件
        output_dir = Path.cwd() / 'output'
        for f in intermediate_files:
            (output_dir / f).unlink()
        (output_dir / "intermediate_files.txt").unlink()

    def run(self):  # 渲染方形视频
        """
        :return: 无返回值，在output文件夹输出渲染完毕的视频
        """
        if not shutil.which('ffmpeg'):
            raise RuntimeError("未找到 ffmpeg，请确保已安装并添加到 PATH")
        if not shutil.which('ffprobe'):
            raise RuntimeError("未找到 ffprobe，请确保已安装并添加到 PATH")

        print("正在将视频转换为CFR视频……")
        self._convert_vfr_to_cfr()

        # 接下来只处理CFR视频
        self._render()
        self._reencode_output()
        self._add_audio_to_video()

        Path(self._cfr_output_path).unlink(missing_ok=True)
        Path(self._output_path).unlink(missing_ok=True)

        print(f"{self._video_file_name}稳定完成")

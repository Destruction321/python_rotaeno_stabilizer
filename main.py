from pathlib import Path
from time import time

from python_rotaeno_stabilizer import RotaenoStabilizer

def find_all_videos():
    """
    寻找videos目录下的所有视频文件，不区分大小写
    
    :return: 视频列表
    """
    video_dir = Path.cwd() / 'videos'  # 指向videos目录
    videos = []
    # 获取所有支持的视频文件扩展名（转换为小写）
    video_extensions = [ext.lower() for ext in RotaenoStabilizer.format_to_fourcc.keys()]

    for file_path in video_dir.glob('*.*'):
        if not file_path.is_file():
            continue

        # 检查文件扩展名是否在支持的列表中
        if file_path.suffix.lower() not in video_extensions:
            continue

        videos.append(str(file_path.relative_to(video_dir)))

    return videos


if __name__ == '__main__':
    videos = find_all_videos()
    print(videos)
    for video in videos:
        start = time()
        try:
            print("正在处理:", video)
            if video[0:2] == "v1":
                stab_task = RotaenoStabilizer(video, mode="v1")
            else:
                stab_task = RotaenoStabilizer(video)

            stab_task.run()
        except Exception as e:
            print("处理视频时发生错误:", e)
        end = time()
        print(f"用时：{end - start}s")

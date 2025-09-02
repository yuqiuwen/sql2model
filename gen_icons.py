"""生成应用程序图标"""
import os
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import tempfile




def make_icns(src_image: str, out_icns: str, keep_iconset: bool = False) -> str:
    """生成mac icns图标

    :param str src_image: 图标文件路径
    :param str out_icns: 输出路径
    :param bool keep_iconset: 否保留中间的 .iconset 目录, defaults to False
    :return str: .icns 文件绝对路径
    """

    src = Path(src_image).expanduser().resolve()
    if not src.exists():
        raise RuntimeError(f"源图片不存在: {src}")
    
    out_icns_path = Path(out_icns).expanduser().resolve()
    out_icns_path.parent.mkdir(parents=True, exist_ok=True)

    # 临时 .iconset 目录
    tmp_dir = Path(tempfile.mkdtemp(prefix="app_icon_"))
    iconset_dir = tmp_dir / "App.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    # 生成不同尺寸的中间图像
    sizes = [
        (16,   "icon_16x16.png"),
        (32,   "icon_16x16@2x.png"),
        (32,   "icon_32x32.png"),
        (64,   "icon_32x32@2x.png"),
        (128,  "icon_128x128.png"),
        (256,  "icon_128x128@2x.png"),
        (256,  "icon_256x256.png"),
        (512,  "icon_256x256@2x.png"),
        (512,  "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    for px, name in sizes:
        dest = iconset_dir / name
        # sips 支持一次性格式转换+缩放
        cmd = [
            "sips",
            "-s", "format", "png",
            "-z", str(px), str(px),
            str(src),
            "--out", str(dest)
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"sips 生成 {name} 失败: {e.stderr.decode('utf-8', 'ignore')}") from e

    try:
        subprocess.run(
                ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(out_icns_path)],
                check=True, capture_output=True
            )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"iconutil 打包 .icns 失败: {e.stderr.decode('utf-8', 'ignore')}") from e
    finally:
        if not keep_iconset:
            shutil.rmtree(iconset_dir.parent, ignore_errors=True)

    return str(out_icns_path)


if __name__ == "__main__":
    src_image = './sql_ico.png'
    make_icns(src_image=src_image, out_icns='./assets/Icon.icns')
    
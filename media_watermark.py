"""Animated GIF and MP4 rendering, with cooperative cancellation."""
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading

from PIL import Image


class Cancelled(Exception):
    pass


def check_cancel(event):
    if event is not None and event.is_set():
        raise Cancelled()


def overlay_for(size, mark, percent, opacity):
    width, height = size
    margin = max(1, round(min(size) * .02))
    scale = min(width * percent / 100 / mark.width,
                max(1, width - 2 * margin) / mark.width,
                max(1, height - 2 * margin) / mark.height)
    overlay = mark.resize((max(1, round(mark.width * scale)),
                           max(1, round(mark.height * scale))), Image.Resampling.LANCZOS)
    overlay.putalpha(overlay.getchannel('A').point(lambda value: round(value * opacity / 100)))
    return overlay, margin


def watermark_gif(source, output, mark, percent, position, opacity, placement, event, progress):
    frames, durations = [], []
    try:
        with Image.open(source) as raw:
            count = raw.n_frames
            if raw.width * raw.height * count > 50_000_000:
                raise ValueError('GIF is too large for safe processing. Reduce its dimensions or frame count.')
            loop = raw.info.get('loop')
            with overlay_for(raw.size, mark, percent, opacity)[0] as overlay:
                margin = max(1, round(min(raw.size) * .02))
                point = placement(raw.size, overlay.size, position, margin)
                for index in range(count):
                    check_cancel(event)
                    raw.seek(index)
                    durations.append(raw.info.get('duration', 100))
                    with raw.convert('RGBA') as canvas:
                        canvas.alpha_composite(overlay, point)
                        # Reserve one palette entry for transparent pixels.
                        frame = canvas.convert('RGB').quantize(colors=255)
                        mask = canvas.getchannel('A').point(lambda a: 255 if a < 128 else 0)
                        frame.paste(255, mask=mask)
                        mask.close()
                        frame.info['transparency'] = 255
                        frames.append(frame)
                    progress((index + 1) / count * .95)
                check_cancel(event)
                options = dict(save_all=True, append_images=frames[1:], duration=durations,
                               disposal=2, transparency=255, optimize=False)
                if loop is not None:
                    options['loop'] = loop
                frames[0].save(output, format='GIF', **options)
                check_cancel(event)
    finally:
        for frame in frames:
            frame.close()


def watermark_mp4(source, output, mark, percent, position, opacity, placement, event, progress):
    import imageio_ffmpeg
    check_cancel(event)
    reader = imageio_ffmpeg.read_frames(str(source), output_params=['-frames:v', '1'])
    try:
        metadata = next(reader)
    finally:
        reader.close()
    size = metadata['size']
    duration = metadata.get('duration', 0)
    if size[0] * size[1] > 40_000_000:
        raise ValueError('Video exceeds 40 megapixels; reduce its dimensions.')
    with tempfile.TemporaryDirectory(prefix='watermark-video-') as temporary:
        overlay_path = Path(temporary) / 'overlay.png'
        with overlay_for(size, mark, percent, opacity)[0] as overlay:
            margin = max(1, round(min(size) * .02))
            x, y = placement(size, overlay.size, position, margin)
            overlay.save(overlay_path)
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-nostdin', '-hide_banner',
                   '-i', str(source), '-loop', '1', '-i', str(overlay_path),
                   '-filter_complex', f'[0:v:0][1:v:0]overlay={x}:{y}:shortest=1,pad=ceil(iw/2)*2:ceil(ih/2)*2[v]',
                   '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-crf', '18',
                   '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
                   '-movflags', '+faststart', '-shortest', '-progress', 'pipe:1', '-nostats', str(output)]
        check_cancel(event)
        with tempfile.TemporaryFile(mode='w+b') as errors:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                       text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            messages = queue.Queue()

            def read_progress():
                for line in process.stdout:
                    messages.put(line.strip())
                messages.put(None)

            thread = threading.Thread(target=read_progress, daemon=True)
            thread.start()
            try:
                while True:
                    check_cancel(event)
                    try:
                        line = messages.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if line is None:
                        break
                    if line.startswith('out_time_us=') and duration:
                        try:
                            progress(min(.99, max(0, int(line.split('=', 1)[1]) / 1_000_000 / duration)))
                        except ValueError:
                            pass
                process.wait()
                check_cancel(event)
                if process.returncode:
                    errors.seek(0)
                    details = errors.read().decode('utf-8', errors='replace')[-1500:]
                    raise RuntimeError('Video encoding failed: ' + details)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                thread.join(timeout=2)
                process.stdout.close()

import cv2
import os

from sys import argv


img_dir = argv[1]
vid_dir = argv[2]
fps = int(argv[3])

frames = []

images = [f for f in os.listdir(img_dir) if '.png' in f]
images.sort(key=lambda f: float(f[:f.find('.png')]))

for img_file in images:
    img = cv2.imread(os.path.join(img_dir, img_file))
    height, width, _ = img.shape
    size = width, height

    frames.append(img)

vid = cv2.VideoWriter(vid_dir, cv2.VideoWriter_fourcc(*'MP4V'), fps, size)

for frame in frames:
    vid.write(frame)

cv2.destroyAllWindows()
vid.release()
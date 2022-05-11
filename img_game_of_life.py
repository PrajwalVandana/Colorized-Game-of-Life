import os
import subprocess
import time

from sys import argv
from PIL import Image
from image_resize import enlarge, compress


start_time = time.time()


def next_step(pixels, size):
    """Takes a `PixelAccess` object and runs the Game of Life algorithm on it:
    https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life
    This means that the image will be changed directly, and will not be
    returned by the function. Instead, a `bool` describing if there were any
    non-dead cells is returned.

    `size`: `(width, height)` tuple"""
    res = False
    mat = [[None]*size[0] for _ in range(size[1])]
    for w in range(size[0]):
        for h in range(size[1]):
            mat[h][w] = pixels[w, h][:3]

            col = mat[h][w]
            live_neighbors = 0
            avg_col = (0,)*3
            for i in range(-1, 2):
                for j in range(-1, 2):
                    if h+i in range(len(mat)) and w+j in range(len(mat[0])) and (i or j):
                        if mat[h+i][w+j] is not None:
                            add_col = mat[h+i][w+j]
                        else:
                            add_col = pixels[w+j, h+i][:3]

                        live_neighbors += add_col != (0,)*3

                        # we can add the color of a cell even if it is dead
                        # because it will not be counted when averaging and
                        # does not change the values (since a dead cell
                        # is (0, 0, 0))
                        avg_col = tuple(avg_col[n] + add_col[n]
                                        for n in range(3))

            if not live_neighbors:
                col = (0,)*3
            else:
                avg_col = tuple(map(lambda n: n//live_neighbors, avg_col))
                if col == (0,)*3 and live_neighbors == 3:
                    # dead, 3 neighbors -> reborn
                    col = avg_col
                elif col != (0,)*3:  # live
                    if live_neighbors < 2 or live_neighbors > 3:
                        # under/overpopulation
                        col = (0,)*3
                    elif FADE:  # fade out stable groups of cells
                        col = tuple(max(val-1, 0) for val in col)

            if col != mat[h][w]:
                res = True

            pixels[w, h] = col

    return res


# OPTIONS
FADE = False
ENLARGE_FACTOR = 4  # 4 is good (minimum value where blurring is gone)
FPS = 10
###

img = Image.open(argv[1])
pixels = img.load()

if not os.path.exists(argv[2]):
    os.mkdir(argv[2])
    enlarge(pixels, img.size, ENLARGE_FACTOR).save(
        os.path.join(argv[2], '0.png'))
    i = 1
else:
    i = int(sorted([f for f in os.listdir(argv[2]) if '.png' in f],
                   key=lambda f: int(f[:f.find('.png')]))[-1][:-4])+1
    enlarged_img = Image.open(os.path.join(argv[2], f'{i-1}.png'))
    img = compress(enlarged_img.load(), enlarged_img.size, ENLARGE_FACTOR)
    pixels = img.load()

start_i = i

while True:
    try:
        if not next_step(pixels, img.size):
            break

        enlarge(pixels, img.size, ENLARGE_FACTOR).save(
            os.path.join(argv[2], str(i)+'.png'))
    except KeyboardInterrupt:
        print()
        # if the user stops the program,
        # convert whatever we have so far to video
        break
    i += 1

subprocess.run(["python3", "img_to_vid.py", argv[2], argv[3], str(FPS)])

end_time = time.time()-start_time

print(f"""Took {end_time} seconds to simulate {i-start_i} generations.
({end_time/(i-start_i)} secs/gen).
In total, {i} generations have been calculated.""")

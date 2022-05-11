import os
import subprocess
import time

from sys import argv
from multiprocessing import Pool
from PIL import Image
from image_resize import enlarge, compress


start_time = time.time()

# OPTIONS
FADE = False
# NOTE: 4 is good for moderately sized images
ENLARGE_FACTOR = 16
FPS = 10
CHUNK_SIZE = 8
NUM_PROCESSES = 16
###


def in_buffer(row, col, w, h, chunk_size):
    if col == 0:
        if row == 0:
            if w == chunk_size-1 or h == chunk_size-1:
                return True
        elif row == chunk_size-1:
            if w == chunk_size-1 or not h:
                return True
        else:
            if w == chunk_size-1 or h in (0, chunk_size-1):
                return True
    elif col == chunk_size-1:
        if row == 0:
            if not w or h == chunk_size-1:
                return True
        elif row == chunk_size-1:
            if not(w and h):
                return True
        else:
            if not w or h in (0, chunk_size-1):
                return True
    else:
        if row == 0:
            if w in (0, chunk_size-1) or h == chunk_size-1:
                return True
        elif row == chunk_size-1:
            if w in (0, chunk_size-1) or not h:
                return True
        else:
            if w in (0, chunk_size-1) or h in (0, chunk_size-1):
                return True

    return False


def next_step(args):
    """
    Takes a 2D array representing an image and runs the Game of Life
    algorithm on it: https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life.

    `args`: the tuple `(chunk, chunk_id, buffer)`
        `chunk`: the chunk to operate on
        `chunk_id`: the tuple `(row, col)`
        `buffer`: the border buffer
    """

    chunk, (row, col), buffer = args

    chunk_size = len(chunk)

    new_chunk = [[None]*chunk_size for _ in range(chunk_size)]
    for w in range(chunk_size):
        for h in range(chunk_size):
            color = chunk[h][w][:3]
            live_neighbors = 0
            avg_color = (0,)*3
            for i in range(-1, 2):
                for j in range(-1, 2):
                    if (i or j):
                        if w+i in range(chunk_size) and h+j in range(chunk_size):
                            add_color = chunk[h+j][w+i][:3]
                        elif (chunk_size * col + w+i, chunk_size * row + h+j) in buffer:
                            add_color = buffer[chunk_size * col + w+i,
                                               chunk_size * row + h+j][:3]
                        else:
                            break

                        # print(os.getpid(), live_neighbors, add_color, end=' ')
                        live_neighbors += add_color != (0,)*3
                        # print(live_neighbors)

                        # we can add the color of a cell even if it is dead
                        # because it will not be counted when averaging and
                        # does not change the values (since a dead cell
                        # is (0, 0, 0))
                        avg_color = tuple(avg_color[n] + add_color[n]
                                          for n in range(3))

            if not live_neighbors:
                color = (0,)*3
            else:
                avg_color = tuple(map(lambda n: n//live_neighbors, avg_color))
                if color == (0,)*3 and live_neighbors == 3:
                    # dead, 3 neighbors -> reborn
                    color = avg_color
                elif color != (0,)*3:  # live cell
                    if live_neighbors < 2 or live_neighbors > 3:
                        # under/overpopulation
                        color = (0,)*3
                    elif FADE:  # fade out stable groups of cells
                        color = tuple(max(val-1, 0) for val in color)

            new_chunk[h][w] = color

    for w in range(chunk_size):
        for h in range(chunk_size):
            chunk[h][w] = new_chunk[h][w]

    return chunk


def chunkify(pixels, img_size, chunk_size):
    """Takes a `PIL.Image.PixelAccess` and chunks it into a rectangular matrix,
    where each entry is a `chunk_size x chunk_size` chunk. Assumes that
    `chunk_size` evenly divides the dimensions of `img`. Returns the chunks
    and a buffer for the borders between chunks."""
    num_chunks_w = img_size[0]//chunk_size
    num_chunks_h = img_size[1]//chunk_size

    buffer = {}
    res = [[None] * num_chunks_w for _ in range(num_chunks_h)]
    for row in range(num_chunks_h):
        for col in range(num_chunks_w):
            res[row][col] = Image.new('RGB', (chunk_size, chunk_size)).load()

    for row in range(num_chunks_h):
        for col in range(num_chunks_w):
            for w in range(chunk_size):
                for h in range(chunk_size):
                    res[row][col][w, h] = \
                        pixels[col*chunk_size + w, row*chunk_size + h][:3]
                    if in_buffer(row, col, w, h, chunk_size):
                        buffer[col*chunk_size + w, row*chunk_size + h] = \
                            pixels[col*chunk_size + w, row*chunk_size + h][:3]
                    # buffer[col*chunk_size + w, row*chunk_size + h] = \
                    #     pixels[col*chunk_size + w, row*chunk_size + h][:3]

    return res, buffer


def combine(chunks, chunk_size):
    """Combines `chunks` (`PixelAccess`) and returns a `PIL.Image.Image`."""
    res = Image.new('RGB', ((width := len(chunks[0])*chunk_size),
                            (height := len(chunks)*chunk_size)))
    res_pixels = res.load()

    for w in range(width):
        for h in range(height):
            res_pixels[w, h] = chunks[h//chunk_size][w//chunk_size][w % chunk_size,
                                                                    h % chunk_size][:3]

    return res


def pixels_to_array(pixels, size):
    array = [[None]*size[0] for _ in range(size[1])]
    for w in range(size[0]):
        for h in range(size[1]):
            array[h][w] = pixels[w, h][:3]

    return array


if __name__ == '__main__':
    if not os.path.exists(argv[2]):
        ref = Image.open(argv[1])
        img = Image.new('RGB',
                        (ref.size[0]+CHUNK_SIZE*bool(ref.size[0] % CHUNK_SIZE) -
                            (ref.size[0] % CHUNK_SIZE),
                         ref.size[1]+CHUNK_SIZE*bool(ref.size[1] % CHUNK_SIZE) -
                            (ref.size[1] % CHUNK_SIZE)))
        img.paste(ref)

        pixels = img.load()
        os.mkdir(argv[2])
        enlarge(pixels, img.size, ENLARGE_FACTOR).save(
            os.path.join(argv[2], '0.png'))
        start_gens = 0
        # i = 1
    else:
        imgs = [f for f in os.listdir(argv[2]) if '.png' in f]
        start_gens = len(imgs)-1
        i = float(sorted(imgs,
                         key=lambda f: float(f[:f.find('.png')]))[-1][:-4])
        enlarged_img = Image.open(os.path.join(argv[2], f'{i}.png'))
        img = compress(enlarged_img.load(), enlarged_img.size, ENLARGE_FACTOR)
        pixels = img.load()

    chunks, BUFFER = chunkify(pixels, img.size, CHUNK_SIZE)

    # start_i = i

    while True:
        try:
            flattened_chunks = []
            for r in range(len(chunks)):
                for c in range(len(chunks[0])):
                    flattened_chunks.append((pixels_to_array(chunks[r][c],
                                                             (CHUNK_SIZE,)*2),
                                             (r, c), BUFFER))

            with Pool(NUM_PROCESSES) as pool:
                res = pool.map(next_step, flattened_chunks)

            for i in range(len(res)):
                r, c = i//len(chunks[0]), i % len(chunks[0])
                for w in range(CHUNK_SIZE):
                    for h in range(CHUNK_SIZE):
                        chunks[r][c][w, h] = res[i][h][w]

            img = combine(chunks, CHUNK_SIZE)
            pixels = img.load()

            enlarge(pixels, img.size, ENLARGE_FACTOR).save(
                os.path.join(argv[2], str(time.time())+'.png'))

            # enlarge(pixels, img.size, ENLARGE_FACTOR).save(
            #     os.path.join(argv[2], str(i)+'.png'))

            # update buffer
            for row in range(len(chunks)):
                for col in range(len(chunks[0])):
                    for w in range(CHUNK_SIZE):
                        for h in range(CHUNK_SIZE):
                            if in_buffer(row, col, w, h, CHUNK_SIZE):
                                BUFFER[col*CHUNK_SIZE+w, row*CHUNK_SIZE+h] = \
                                    pixels[col*CHUNK_SIZE +
                                           w, row*CHUNK_SIZE+h]
                            # BUFFER[col*CHUNK_SIZE+w, row*CHUNK_SIZE+h] = \
                            #     pixels[col*CHUNK_SIZE +
                            #            w, row*CHUNK_SIZE+h]
            i += 1
        except KeyboardInterrupt:
            print()
            # if the user stops the program,
            # convert whatever we have so far to video
            break

    subprocess.run(["python3", "img_to_vid.py", argv[2], argv[3], str(FPS)])

    end_time = time.time()-start_time

    # print(f"""Took {end_time} seconds to simulate {i-start_i} generations.
    # ({end_time/(i-start_i)} secs/gen).
    # In total, {i} generations have been calculated.""")
    num_gens = len(os.listdir(argv[2]))-start_gens
    print(f"""
Took {end_time} seconds to simulate {num_gens} generations.
({end_time/num_gens} secs/gen).
In total, {num_gens+start_gens} generations have been calculated.""")

from fpng_py import fpng_encode_image_to_memory


def get_png_buffer(image):
    im = image.convert({'L': 'RGB', 'LA': 'RGBA'}[image.mode]) if image.mode in ['L', 'LA'] else image
    return fpng_encode_image_to_memory(im.tobytes(), im.size[0], im.size[1], len(im.mode), 2)

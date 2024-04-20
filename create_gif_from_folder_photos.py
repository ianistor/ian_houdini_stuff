from PIL import Image
import os

"""
This was used in a tops chain to generate a GIF with all the variations created during the wedging
This still needs a render process before.
"""

def create_gif(image_folder, output_file, duration):
    """
    Create a GIF from images in a folder.
    Args:
    - image_folder (str): Path to the folder containing images.
    - output_file (str): Path to the output GIF file.
    - duration (int): Duration for each frame in milliseconds.
    """
    images = []

    image_files = sorted(os.listdir(image_folder))
    for filename in sorted(os.listdir(image_folder)):
        if filename.endswith(".png") or filename.endswith(".jpg") or filename.endswith(".jpeg"):
            filepath = os.path.join(image_folder, filename)
            im = Image.open(filepath)
            im = im.resize((1280, 720))
            im = add_background(im)
            images.append(im)

    if images:
        images[0].save(output_file, save_all=True, append_images=images[1:], optimize=False, duration=duration, loop=0)
        print(f"GIF created successfully at: {output_file}")
    else:
        print("No images found in the specified folder.")


def add_background(image):

    image_with_bg = Image.new("RGB", image.size, "black")
    image_with_bg.paste(image, (0, 0), image)
    return image_with_bg


# Example usage:
image_folder = 'D:\\Projects\\houdini projects\\'
output_file = 'D:\\Projects\\today_renders.gif'
frame_duration = 600  

create_gif(image_folder, output_file, frame_duration)


from PIL import Image
from io import BytesIO
import aiofiles

from bot.config import settings, logger

async def resize_and_save_image(image_data: bytes, path: str):
    img = Image.open(BytesIO(image_data))
    max_dim = max(img.size)

    logger.debug(f"Original image size: {img.size}, max dimension: {max_dim}")

    if max_dim > settings.image_max_dimension:
        scale = settings.image_max_dimension / max_dim
        new_size = tuple([int(d * scale) for d in img.size])
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    async with aiofiles.open(path, "wb") as f:
        buffer = BytesIO()
        img.save(buffer, format="WEBP")
        await f.write(buffer.getvalue())

# Test Images for Image Support

All images in this directory are from public domain or free-to-use sources.

## Image Sources and Licensing

### Original Set (5 images)
| Filename | Source | License | Notes |
|----------|--------|---------|-------|
| test1.jpg | [Unsplash](https://images.unsplash.com/photo-1506905925346-21bda4d32df4) | Free to use | Unsplash License - Free for commercial and non-commercial use, no attribution required |
| test2.jpg | [Unsplash](https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05) | Free to use | Unsplash License - Free for commercial and non-commercial use, no attribution required |
| test3.jpg | [Wikipedia Commons](https://upload.wikimedia.org/wikipedia/en/a/a9/Example.jpg) | Public Domain | Created by Centrx, cropped by JPxG - explicitly public domain |
| test4.jpg | [Lorem Picsum](https://picsum.photos/300/200?random=1) | Free to use | Placeholder image service - free for any use |
| test5.png | [Wikipedia Commons](https://upload.wikimedia.org/wikipedia/commons/8/89/HD_transparent_picture.png) | Public Domain | Explicitly public domain on Wikimedia Commons |

### Additional Animal Images (10 images for vision testing)
| Filename | Source | License | Notes |
|----------|--------|---------|-------|
| cat1.jpg | [Wikipedia Commons](https://upload.wikimedia.org/wikipedia/commons/4/4d/Cat_November_2010-1a.jpg) | Public Domain / CC-BY-SA | Domestic cat portrait |
| dog1.jpg | [Unsplash](https://images.unsplash.com/photo-1583337130417-3346a1be7dee) | Free to use | Unsplash License - Labrador Retriever |
| bird1.jpg | [Unsplash](https://images.unsplash.com/photo-1552728089-57bdde30beb3) | Free to use | Unsplash License - Great Tit bird |
| fish1.jpg | [Unsplash](https://images.unsplash.com/photo-1559827260-dc66d52bef19) | Free to use | Unsplash License - Koi fish |
| lion1.jpg | [Unsplash](https://images.unsplash.com/photo-1611605698335-8b1569810432) | Free to use | Unsplash License - Lion portrait |
| horse1.jpg | [Unsplash](https://images.unsplash.com/photo-1553284965-83fd3e82fa5a) | Free to use | Unsplash License - Horse portrait |
| deer1.jpg | [Unsplash](https://images.unsplash.com/photo-1545558014-8692077e9b5c) | Free to use | Unsplash License - Deer in nature |
| giraffe1.jpg | [Unsplash](https://images.unsplash.com/photo-1529390079861-591de354faf5) | Free to use | Unsplash License - Giraffe |
| zebra1.jpg | [Unsplash](https://images.unsplash.com/photo-1503917988258-f87a78e3c995) | Free to use | Unsplash License - Zebra portrait |
| elephant1.jpg | [Wikipedia Commons](https://upload.wikimedia.org/wikipedia/commons/3/37/African_Bush_Elephant.jpg) | Public Domain | African bush elephant |

## Usage
These images are used for testing the imagebank functionality in chatybot's image-to-text (vision) feature.

### Test Files for Accuracy Evaluation
**All 15 images** have corresponding `.txt` files with expected content for automated accuracy testing:

```
subject: <main_subject>
color: <primary_color>
```

Format used in `.txt` files:
- **Animal images** (cat1-elephant1): Single word subject (cat, dog, bird, etc.) + primary color
- **Original test images** (test1-test5): General description (landscape, nature, testpattern, etc.) + color

These can be used in chatDSL scripts to:
1. Load an image: `/imagebank1 <file>.jpg`
2. Get LLM description: `Describe {imagebank1}`
3. Parse response and compare with `.txt` file contents
4. Calculate accuracy metrics

Example chatDSL usage:
```
/selectimage cat1.jpg
/loadimage cat1.jpg imagebank1
Describe the subject and main color of this image: {imagebank1}
```
Then compare the response with `cat1.txt` contents.

## Verification
- Original 5 images: Downloaded on 2025-04-19
- Additional 10 animal images: Downloaded on 2026-04-26
- All 15 `.txt` test files created: 2026-04-26
- All images verified as valid JPEG/PNG files with `file` command
- All `.txt` files verified as valid text files
- Unsplash images: Free to use under [Unsplash License](https://unsplash.com/license)
- Wikipedia Commons images: Public domain or CC-BY-SA as indicated

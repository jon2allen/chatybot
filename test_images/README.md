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

### Animal and Object Images (10 images for vision testing)
| Filename | Source | License | Notes |
|----------|--------|---------|-------|
| bird1.jpg | [Unsplash](https://images.unsplash.com/photo-1552728089-57bdde30beb3) | Free to use | Unsplash License - Great Tit bird |
| cat1.jpg | [Wikipedia Commons](https://upload.wikimedia.org/wikipedia/commons/4/4d/Cat_November_2010-1a.jpg) | Public Domain / CC-BY-SA | Domestic cat portrait |
| dog1.jpg | [Unsplash](https://images.unsplash.com/photo-1583337130417-3346a1be7dee) | Free to use | Unsplash License - Labrador Retriever |
| elephant1.jpg | [Wikipedia Commons](https://upload.wikimedia.org/wikipedia/commons/3/37/African_Bush_Elephant.jpg) | Public Domain | African bush elephant |
| horse1.jpg | [Unsplash](https://images.unsplash.com/photo-1553284965-83fd3e82fa5a) | Free to use | Unsplash License - Horse portrait |
| kid.jpg | User-provided | User-provided | Human child portrait |
| logo.jpg | User-provided | User-provided | Twitter bird logo |
| ocean.jpg | User-provided | User-provided | Ocean scene |
| toys.jpg | User-provided | User-provided | Toy collection |
| zebra1.jpg | [Unsplash](https://images.unsplash.com/photo-1503917988258-f87a78e3c995) | Free to use | Unsplash License - Zebra portrait |

**Note:** deer1.jpg, fish1.jpg, giraffe1.jpg, and lion1.jpg .txt files exist but corresponding image files were removed. The .txt files remain for potential future use.

## Usage
These images are used for testing the imagebank functionality in chatybot's image-to-text (vision) feature.

### Test Files for Accuracy Evaluation
**All 15 images** have corresponding `.txt` files with expected content for automated accuracy testing:

```
subject: <main_subject>
color: <primary_color>
```

Format used in `.txt` files:
- General description + color for all images
- Supports multi-word subjects (e.g., "human child", "testpattern/text", "twitter bird logo")

These can be used in chatDSL scripts to:
1. Load an image: `/imagebank1 <file>.jpg`
2. Get LLM description: `Describe {imagebank1}`
3. Parse response and compare with `.txt` file contents
4. Calculate accuracy metrics

Example chatDSL usage:
```
/imagebank1 test_images/cat1.jpg
Describe the subject and main color of this image: {imagebank1}
```
Then compare the response with `cat1.txt` contents.

## chatDSL Accuracy Test Script
The `accuracytest.chatdsl` script automates accuracy testing for all 15 images:

### Script Structure
- **Phase 1:** Query each image with `openrouter_image` model to identify subject and color
- **Phase 2:** Compare each vision output with expected `.txt` file using `elephant` model
- **Phase 3:** Generate summary reports in batches (5 images each)

### Execution
```
/script test_images/accuracytest.chatdsl
```

### Output
- Individual vision responses: `accuracy_results/result_*.txt`
- Individual comparisons: `accuracy_results/comparison_*.txt`
- Batch summaries: `accuracy_results/summary_batch*.txt`
- Final summary: `accuracy_results/final_summary.txt`

### Rate Limiting
- Each API call followed by `wait 2` (2-second delay)
- Total runtime: ~30 seconds wait + API time (~3-4 minutes total)

## Current Image-Text Pairings

| Image | Expected Subject | Expected Color |
|-------|------------------|---------------|
| test1.jpg | landscape | white |
| test2.jpg | nature | green |
| test3.jpg | testpattern/text | multicolor |
| test4.jpg | typewriter | black |
| test5.png | transparent | none |
| bird1.jpg | bird | yellow |
| cat1.jpg | cat | grey |
| dog1.jpg | dog | yellow |
| elephant1.jpg | elephant | grey |
| horse1.jpg | horse | white |
| kid.jpg | human child | brown |
| logo.jpg | twitter bird logo | blue - several shades of blue |
| ocean.jpg | ocean | dark blue |
| toys.jpg | toys | multi-color |
| zebra1.jpg | city | tan buildings |

## Verification
- Original 5 images: test1.jpg - test5.png
- Animal/object images: bird1.jpg, cat1.jpg, dog1.jpg, elephant1.jpg, horse1.jpg, kid.jpg, logo.jpg, ocean.jpg, toys.jpg, zebra1.jpg
- Total: **15 images** with matching .txt files
- All images verified as valid JPEG/PNG files
- All `.txt` files verified as valid text files
- Unsplash images: Free to use under [Unsplash License](https://unsplash.com/license)
- Wikipedia Commons images: Public domain or CC-BY-SA as indicated
- User-provided images: kid.jpg, logo.jpg, ocean.jpg, toys.jpg

## Notes
- The `zebra1.jpg` image has an expected subject of "city" and color "tan buildings" - verify the image matches this description
- The `logo.jpg` image has expected subject "twitter bird logo" - this may need verification
- Four .txt files (deer1, fish1, giraffe1, lion1) exist without corresponding images

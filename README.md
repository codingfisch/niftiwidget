# NiftiWidget

NiftiWidget brings the 3D image viewing capabilities of [NiftiView](https://github.com/codingfisch/niftiview_app) into [Jupyter](https://jupyter.org/) notebooks 👩‍💻

NiftiWidget is build around the `niftiview` [Python package](https://github.com/codingfisch/niftiview), that allows users to
- View **multiple** 3D images in a **beautiful layout** 🧩
- Add **custom image layers** and **overlays** (crosshair, colorbar...) 📑
- Save the view as a **high-quality figure** or as a **GIF** 💾
- ...and much more...

Learn to use it via the `niftiview` [examples](https://github.com/codingfisch/niftiview/tree/main/examples) and [this **YouTube-Tutorial**](https://www.youtube.com/) 💡

Install it via `pip install niftiwidget` 🛠️
- In Colab, run `apt install libcairo2-dev pkg-config python3-dev` then `pip install niftiwidget`
- On other systems [these tips](https://github.com/codingfisch/niftiview_app?tab=readme-ov-file#bugfixes-) might help to make it work
## Usage 💡
To view saved files, pass the filepaths to `Config` which is passed to `NiftiWidget`
```python
from niftiview import TEMPLATES, Config
from niftiwidget import NiftiWidget

filepaths = [[TEMPLATES['ch2']], [TEMPLATES['T1']]]
# filepaths = [['/path/to/nifti1.nii.gz'], ['/path/to/nifti2.nii.gz']]
config = Config(filepaths_view1=filepaths)
NiftiWidget(config=config)
```
Alternatively, one can also pass a list of `nibabel` images directly to `NiftiWidget`
```python
import nibabel as nib
from niftiview import TEMPLATES, Config
from niftiwidget import NiftiWidget

nib_images = [[nib.load(TEMPLATES['ch2'])], [nib.load(TEMPLATES['T1'])]]
config = Config()
NiftiWidget(nib_images1=nib_images)
```
To **avoid the widget getting to large** you can limit the image width by passing a `Layout`
```python
from ipywidgets import Layout
...
NiftiWidget(..., layout=Layout(max_width='1000px'))
```
Start exploring by pasting the below code into a cell and try **different [settings](https://github.com/codingfisch/niftiview/blob/main/niftiview/config.py#L21)** by changing the config...
```python
from ipywidgets import Layout
from niftiview import TEMPLATES
from niftiview.config import Config
from niftiwidget import NiftiWidget

filepaths = [[TEMPLATES['ch2']], [TEMPLATES['T1']]]
# filepaths = [['/path/to/nifti1.nii.gz'], ['/path/to/nifti2.nii.gz']]
config = Config(filepaths_view1=filepaths, layout='all', fpath=1, crosshair=True)
NiftiWidget(config=config, layout=Layout(max_width='1000px'))
```
...or interacting with the widget itself!

### Pitfall: Use `;` at the end of filepaths!
Inside the NiftiView widget, instead of hitting Enter to confirm a filepath, write `;` at the end of it. If you write
```
/path/to/figures/figure1.pdf
```
in the **Save image or GIF** textbox and hit Enter, nothing will happen. Write `;` at the end of it 
```
/path/to/figures/figure1.pdf;
```
and the figure will be saved 🎉 This also applies to the **Filepattern** textboxes!

If you **change a filepath**, make sure to 
1. delete the `;`
2. change the filepath
3. add the `;`

because modifying the filepath while keeping the `;` will result in e.g. unwanted figures being saved!

## Colab 🐌
Since NiftiWidget does not use the GPU (like e.g. [`ipyniivue`](https://github.com/niivue/ipyniivue)) **image refreshes in Colab are slow** 🐌
![colab](https://github.com/user-attachments/assets/256cc923-da88-47c3-a21a-b610410de7d8)

However, if used inside a local Jupyter notebook this is not an issue 🐇
![jupyter](https://github.com/user-attachments/assets/28e18b8f-402d-4e58-a693-7906e974eb4d)

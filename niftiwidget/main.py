import time
from functools import partial
from nibabel.filebasedimages import SerializableImage
from ipywidgets import (Tab, HBox, VBox, Text, Image, Label, Button, GridBox, Layout, Checkbox,
                        Dropdown, Accordion, FloatText, IntSlider, ToggleButtons, BoundedIntText)
from niftiview.core import (PLANES, ATLASES, TEMPLATES, RESIZINGS, LAYOUT_STRINGS,
                            TEMPLATE_DEFAULT, COORDINATE_SYSTEMS, GLASS_MODES)
from niftiview.image import QRANGE, CMAPS_IMAGE, CMAPS_MASK
from niftiview.grid import NiftiImageGrid
from niftiview.cli import save_gif, save_images_or_gifs
from niftiview.config import Config, LAYER_ATTRIBUTES

from .utils import get_png_buffer
PLANES_4D = tuple(list(PLANES) + ['time'])


class NiftiWidget(VBox):
    def __init__(self, nib_images1=None, nib_images2=None, config=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = Config() if config is None else config
        self.nib_images1 = None if nib_images1 is None else self.set_nib_images(nib_images1)
        self.nib_images2 = None if nib_images2 is None else self.set_nib_images(nib_images2)

        self.niigrid1 = None
        self.niigrid2 = None

        self.load_niigrid()
        self.image = self.niigrid.get_image(**self.config.to_dict(grid_kwargs_only=True))
        self.image_widget = Image(value=get_png_buffer(self.image))

        # VIEW + INPUT + PAGES
        self.view_button = ToggleButtons(options=['View 1', 'View 2'], value=f'View 1', style={"button_width": '48.5%'})
        self.template_options = Dropdown(description='Templates', options=list(TEMPLATES), value=TEMPLATE_DEFAULT)
        self.image_pattern_entry = Text(description='Filepattern', placeholder='/path/to/sub*/*T1w.nii;')
        self.atlas_options = Dropdown(description='Atlases', options=[''] + list(ATLASES), layout=Layout(width='70%'))
        self.clear_button = Button(description='Clear', indent=False, layout=Layout(width='auto'))
        self.mask_box = HBox([self.atlas_options, self.clear_button], layout=Layout(width='auto'))
        self.mask_pattern_entry = Text(description='Filepattern', placeholder='/path/to/sub*/*mask.nii;')
        self.input_box = VBox(
            [self.view_button, self.template_options, self.image_pattern_entry, self.mask_box, self.mask_pattern_entry],
            layout=Layout(width='auto', min_width='29%'))

        self.view_button.observe(self.set_view, names='value')
        self.template_options.observe(self.set_template_options, names='value')
        self.image_pattern_entry.observe(self.open_file_pattern, names='value')
        self.atlas_options.observe(self.set_atlas_options, names='value')
        self.mask_pattern_entry.observe(partial(self.open_file_pattern, is_mask=True), names='value')
        self.clear_button.on_click(self.remove_mask_layers)  # self.set_short_clear)
        # MAIN TAB
        tab_layout = Layout(grid_template_columns='repeat(3, 1fr)', width='100%')  # , grid_gap='5px')
        kw = {'layout': Layout(width='auto', max_width='200px')}
        self.layout_options = Dropdown(description='Layout', options=list(LAYOUT_STRINGS), diabled=False,
                                       value=self.config.layout if self.config.layout in LAYOUT_STRINGS else None, **kw)
        self.layout_entry = Text(
            value=LAYOUT_STRINGS[self.config.layout] if self.config.layout in LAYOUT_STRINGS else self.config.layout,
            **kw)
        self.height_spinbox = BoundedIntText(description='Height', value=self.config.height, min=100, max=2000,
                                             step=100, **kw)
        self.max_samples_spinbox = BoundedIntText(description='Max. samples', value=self.config.max_samples, min=1,
                                                  **kw)
        self.nrows_spinbox = BoundedIntText(description='Rows', min=1, **kw)
        self.squeeze_checkbox = labelleft_checkbox(description='Squeeze', value=self.config.squeeze, **kw)
        self.coord_sys_options = Dropdown(description='Coord. system', options=COORDINATE_SYSTEMS,
                                          value=self.config.coord_sys, **kw)
        self.glassbrain_options = Dropdown(description='Glassbrain', options=[''] + list(GLASS_MODES),
                                           value=self.config.glass_mode, **kw)
        self.main_tab = GridBox([self.layout_options, self.layout_entry, self.height_spinbox,
                                 self.max_samples_spinbox, self.nrows_spinbox, self.squeeze_checkbox,
                                 self.coord_sys_options, self.glassbrain_options], layout=tab_layout)
        # IMAGE TAB
        self.cmap_options = Dropdown(description='Colormap', options=CMAPS_IMAGE, **kw)
        self.cmap_entry = Text(**kw)
        self.equal_hist_checkbox = labelleft_checkbox(description='Equal. hist.', value=self.config.equal_hist, **kw)
        qrange_start = QRANGE[0][0] if self.config.qrange[0] is None else self.config.qrange[0][0]
        qrange_stop = QRANGE[0][1] if self.config.qrange[0] is None else self.config.qrange[0][1]
        self.qrange_start_spinbox = FloatText(description='Quantile range', value=100 * qrange_start, step=2, **kw)
        self.qrange_stop_spinbox = FloatText(value=100 * qrange_stop, step=2, **kw)
        self.transparent_if_entry = Text(description='Transp. if:', value=self.config.transp_if[0], **kw)
        self.vrange_start_spinbox = FloatText(description='Value range', step=.5, **kw)
        self.vrange_stop_spinbox = FloatText(step=.5, **kw)
        self.resizing_options = Dropdown(description='Resizing', options=RESIZINGS, value=RESIZINGS[self.config.resizing[0]], **kw)
        self.image_tab = GridBox([self.cmap_options, self.cmap_entry, self.equal_hist_checkbox,
                                  self.qrange_start_spinbox, self.qrange_stop_spinbox, self.transparent_if_entry,
                                  self.vrange_start_spinbox, self.vrange_stop_spinbox, self.resizing_options],
                                 layout=tab_layout)
        # MASK TAB
        self.cmap_mask_options = Dropdown(description='Colormap', options=CMAPS_MASK, **kw)
        self.cmap_mask_entry = Text(**kw)
        self.alpha_spinbox = FloatText(description='Opacity', value=100 * self.config.alpha, step=10, **kw)
        qvalues = [QRANGE[1][0] if self.config.qrange[-1] is None else self.config.qrange[-1][0],
                   QRANGE[1][1] if self.config.qrange[-1] is None else self.config.qrange[-1][1]]
        self.qrange_start_mask_spinbox = FloatText(description='Quantile range', value=100 * qvalues[0], step=2, **kw)
        self.qrange_stop_mask_spinbox = FloatText(value=100 * qvalues[1], step=2, **kw)
        self.transparent_if_mask_entry = Text(description='Transp. if:', value=self.config.transp_if[-1], **kw)
        self.vrange_start_mask_spinbox = FloatText(description='Value range', step=.5, **kw)
        self.vrange_stop_mask_spinbox = FloatText(step=.5, **kw)
        resizing_mask = RESIZINGS[self.config.resizing[-1]] if len(RESIZINGS) > 1 else 'nearest'
        self.resizing_mask_options = Dropdown(description='Resizing', options=RESIZINGS, value=resizing_mask, **kw)
        self.mask_tab = GridBox([self.cmap_mask_options, self.cmap_mask_entry, self.alpha_spinbox,
                                 self.qrange_start_mask_spinbox, self.qrange_stop_mask_spinbox,
                                 self.transparent_if_mask_entry, self.vrange_start_mask_spinbox,
                                 self.vrange_stop_mask_spinbox, self.resizing_mask_options], layout=tab_layout)
        # OVERLAY TAB
        self.crosshair_checkbox = labelleft_checkbox(description='Crosshair', value=self.config.crosshair, **kw)
        self.coordinates_checkbox = labelleft_checkbox(description='Coordinates', value=self.config.coordinates, **kw)
        self.header_checkbox = labelleft_checkbox(description='Header', value=self.config.header, **kw)
        self.histogram_checkbox = labelleft_checkbox(description='Histogram', value=self.config.histogram, **kw)
        self.fpath_spinbox = BoundedIntText(description='Filepath', min=0, **kw)
        self.title_entry = Text(description='Title', value=self.config.title or "", **kw)
        self.fontsize_spinbox = BoundedIntText(description='Fontsize', value=self.config.fontsize, min=1, **kw)
        self.linewidth_spinbox = BoundedIntText(description='Linewidth', value=self.config.linewidth, min=1, **kw)
        self.linecolor_options = Dropdown(description='Linecolor', options=['white', 'gray', 'black'],
                                          value=self.config.linecolor, **kw)
        self.overlay_tab = GridBox([self.crosshair_checkbox, self.coordinates_checkbox, self.header_checkbox,
                                    self.histogram_checkbox, self.fpath_spinbox, self.title_entry,
                                    self.fontsize_spinbox,
                                    self.linewidth_spinbox, self.linecolor_options], layout=tab_layout)
        # COLORBAR TAB
        self.cbar_options = Dropdown(description='Bar', options=['', 'vertical', 'horizontal'],
                                     value=['horizontal', 'vertical'][
                                         int(self.config.cbar_vertical)] if self.config.cbar else '', **kw)
        self.cbar_x_spinbox = FloatText(description='Position', value=100 * self.config.cbar_x, min=0, max=100, step=1,
                                        **kw)
        self.cbar_y_spinbox = FloatText(value=100 * self.config.cbar_y, min=0, max=100, step=1, **kw)
        self.cbar_width_spinbox = FloatText(description='Size', value=100 * self.config.cbar_width, min=0, max=100,
                                            step=1, **kw)
        self.cbar_length_spinbox = FloatText(value=100 * self.config.cbar_length, min=0, max=100, step=5, **kw)
        self.cbar_pad_spinbox = BoundedIntText(description='Padding', value=self.config.cbar_pad, min=0, max=500,
                                               step=20, **kw)
        self.cbar_pad_color_options = Dropdown(description='Pad. Color',
                                               options=['black', 'white', 'gray', 'transparent'], **kw)
        self.cbar_label_entry = Text(description='Label', value=self.config.cbar_label or "", **kw)
        self.cbar_ticks_entry = Text(description='Ticks', value='|'.join(
            [str(item) for item in self.config.cbar_ticks]) if self.config.cbar_ticks else "", **kw)
        self.colorbar_tab = GridBox([self.cbar_options, self.cbar_x_spinbox, self.cbar_y_spinbox,
                                     self.cbar_width_spinbox, self.cbar_length_spinbox, self.cbar_pad_spinbox,
                                     self.cbar_pad_color_options, self.cbar_label_entry, self.cbar_ticks_entry],
                                    layout=tab_layout)
        # SLIDERS TAB
        kw = {'orientation': 'horizontal', 'min': -200, 'max': 200, 'value': 0,
              'layout': Layout(height='24px', min_width='500px')}
        self.sliders = {}
        for plane in PLANES_4D:
            if plane == 'time':
                kw['min'] = 0
                kw['max'] = 400
            self.sliders.update({plane: IntSlider(description=plane.capitalize(), **kw)})
            self.sliders[plane].observe(partial(self.update_origin, plane=plane), names='value')
        self.slider_tab = VBox(list(self.sliders.values()))

        # GENERAL TAB
        self.layout_options.observe(self.set_layout, names='value')
        self.layout_entry.observe(partial(self.update_config, attribute='layout'), names='value')
        self.squeeze_checkbox.children[1].observe(partial(self.update_config, attribute='squeeze', switch=True),
                                                  names='value')
        self.max_samples_spinbox.observe(self.set_max_samples, names='value')
        self.height_spinbox.observe(partial(self.update_config, attribute='height'), names='value')
        self.nrows_spinbox.observe(partial(self.update_config, attribute='nrows'), names='value')
        self.coord_sys_options.observe(partial(self.update_config, attribute='coord_sys'), names='value')
        self.glassbrain_options.observe(partial(self.update_config, attribute='glass_mode'), names='value')
        # IMAGE TAB
        self.cmap_options.observe(self.set_cmap, names='value')
        self.cmap_entry.observe(partial(self.update_config, attribute='cmap'), names='value')
        self.equal_hist_checkbox.children[1].observe(partial(self.update_config, attribute='equal_hist', switch=True),
                                                     names='value')
        self.qrange_start_spinbox.observe(self.set_quantile_range, names='value')
        self.qrange_stop_spinbox.observe(partial(self.set_quantile_range, stop=True), names='value')
        self.transparent_if_entry.observe(partial(self.update_config, attribute='transp_if'), names='value')
        self.resizing_options.observe(self.set_resizing, names='value')
        # MASK TAB
        self.cmap_mask_options.observe(partial(self.set_cmap, is_mask=True), names='value')
        self.cmap_mask_entry.observe(partial(self.update_config, attribute='cmap', is_mask=True), names='value')
        self.alpha_spinbox.observe(partial(self.update_config, attribute='alpha'), names='value')
        self.qrange_start_mask_spinbox.observe(partial(self.set_quantile_range, is_mask=True), names='value')
        self.qrange_stop_mask_spinbox.observe(partial(self.set_quantile_range, stop=True, is_mask=True), names='value')
        self.transparent_if_mask_entry.observe(partial(self.update_config, attribute='transp_if', is_mask=True),
                                               names='value')
        self.resizing_mask_options.observe(partial(self.set_resizing, is_mask=True), names='value')
        # OVERLAY TAB
        self.crosshair_checkbox.children[1].observe(partial(self.update_config, attribute='crosshair', switch=True),
                                                    names='value')
        self.coordinates_checkbox.children[1].observe(partial(self.update_config, attribute='coordinates', switch=True),
                                                      names='value')
        self.header_checkbox.children[1].observe(partial(self.update_config, attribute='header', switch=True),
                                                 names='value')
        self.histogram_checkbox.children[1].observe(partial(self.update_config, attribute='histogram', switch=True),
                                                    names='value')
        self.fpath_spinbox.observe(partial(self.update_config, attribute='fpath'), names='value')
        self.title_entry.observe(partial(self.update_config, attribute='title'), names='value')
        self.fontsize_spinbox.observe(partial(self.update_config, attribute='fontsize'), names='value')
        self.linewidth_spinbox.observe(partial(self.update_config, attribute='linewidth'), names='value')
        self.linecolor_options.observe(partial(self.update_config, attribute='linecolor'), names='value')
        # COLORBAR TAB
        self.cbar_options.observe(self.set_cbar, names='value')
        self.cbar_x_spinbox.observe(partial(self.update_config, attribute='cbar_x'), names='value')
        self.cbar_y_spinbox.observe(partial(self.update_config, attribute='cbar_y'), names='value')
        self.cbar_width_spinbox.observe(partial(self.update_config, attribute='cbar_width'), names='value')
        self.cbar_length_spinbox.observe(partial(self.update_config, attribute='cbar_length'), names='value')
        self.cbar_pad_spinbox.observe(partial(self.update_config, attribute='cbar_pad'), names='value')
        self.cbar_pad_color_options.observe(partial(self.update_config, attribute='cbar_pad_color'), names='value')
        self.cbar_label_entry.observe(partial(self.update_config, attribute='cbar_label'), names='value')
        self.cbar_ticks_entry.observe(self.set_cbar_ticks, names='value')

        self.tabs = Tab([self.slider_tab, self.main_tab, self.image_tab,
                         self.mask_tab, self.overlay_tab, self.colorbar_tab], layout=Layout(max_width='70%'))
        for i, title in enumerate(['Slider', 'Main', 'Image', 'Mask', 'Overlay', 'Colorbar']):
            self.tabs.set_title(i, title)

        self.page_title = Label('Page', layout=Layout(justify_content="center"))
        self.previous_button = Button(description='Previous')
        self.page_label = Label('1/1', layout=Layout(min_width='20%', justify_content='center'))
        self.next_button = Button(description='Next')
        self.page_buttons = HBox([self.previous_button, self.page_label, self.next_button])
        self.save_image_label = Label('Save image or GIF', layout=Layout(justify_content='center'))
        self.save_image_entry = Text(placeholder='imgs/img.png; or gifs/gif.gif;', layout=Layout(width='auto'))
        self.save_box = VBox([self.page_title, self.page_buttons, self.save_image_label, self.save_image_entry],
                             layout=Layout(max_width='25%', border='solid 1px #D3D3D3'))

        self.previous_button.on_click(self.set_page)
        self.next_button.on_click(partial(self.set_page, next=True))
        self.save_image_entry.observe(self.save_image_or_gif, names='value')

        self.options = HBox([self.input_box, self.tabs, self.save_box], layout=Layout(max_width='100%'))

        self.toolbar = Accordion(children=[self.options], titles=('Toolbar',))

        self.children = [self.image_widget, Accordion(children=[self.options], titles=('Toolbar',))]

    @property
    def niigrid(self):
        return [self.niigrid1, self.niigrid2][self.config.view - 1]

    @staticmethod
    def set_nib_images(images):
        return [[img] for img in images] if isinstance(images[0], SerializableImage) else images

    def load_niigrid(self):
        imgs = [self.nib_images1, self.nib_images2][self.config.view - 1]
        if imgs is None:
            niigrid = NiftiImageGrid(self.config.get_filepaths())
        else:
            filepaths = [[im.dataobj.file_like if hasattr(im.dataobj, 'file_like') else None for im in img] for img in imgs]
            setattr(self.config, f'filepaths_view{self.config.view}', filepaths)
            self.config.resizing = [1] + (self.config.n_layers - 1) * [0]
            self.config.cmap = [CMAPS_IMAGE[0]] + (self.config.n_layers - 1) * [CMAPS_MASK[0]]
            self.config.vrange = None
            self.config.qrange = QRANGE
            self.config.is_atlas = self.config.n_layers * [False]
            self.config.transp_if = [None] + (self.config.n_layers - 1) * ['=0']
            imgs_pages = [imgs[i:i + self.config.max_samples] for i in range(0, len(imgs), self.config.max_samples)]
            niigrid = NiftiImageGrid(nib_images=imgs_pages[min(self.config.page, len(imgs_pages) - 1)])
        setattr(self, f'niigrid{self.config.view}', niigrid)

    def set_view(self, change):
        self.config.view = int(change.new[-1])
        if getattr(self, f'niigrid{self.config.view}') is None:
            self.load_niigrid()
        self.update_image()

    def set_template_options(self, change):
        if self.template_options != change.new:
            self.open_files([TEMPLATES[change.new]])

    def set_atlas_options(self, change):
        if self.atlas_options != change.new:
            if change.new == '':
                self.remove_mask_layers()
            else:
                self.open_files([ATLASES[change.new]], is_mask=True)

    def open_file_pattern(self, change, is_mask=False):
        if change.new.endswith(';'):
            self.open_files(change.new[:-1], is_mask)

    def open_files(self, filepaths, is_mask=False):
        self.config.add_filepaths(filepaths, is_mask)
        self.load_niigrid()
        self.update_image()

    def remove_mask_layers(self, change=None):
        self.config.remove_mask_layers()
        self.atlas_options.value = ''
        self.load_niigrid()
        self.update_image()

    def set_short_clear(self, change):
        self.update_config(change, 'alpha', 0)
        time.sleep(.5)
        self.update_config(change, 'alpha', float(self.alpha_spinbox.value))

    def set_quantile_range(self, change, is_mask=False, stop=False):
        if self.config.qrange[-1 if is_mask else 0] is None:
            qrange = list(QRANGE[int(is_mask)])
        else:
            qrange = list(self.config.qrange[-1 if is_mask else 0])
        qrange[int(stop)] = change.new / 100
        qrange[int(stop)] = min(max(0, qrange[int(stop)]), 1)
        self.update_config(change=None, attribute='qrange', value=qrange, is_mask=is_mask)
        self.config.set_layer_attribute('vrange', None, is_mask)

    def set_page(self, change, next=False):
        page = self.config.page + 1 if next else self.config.page - 1
        if page in list(range(self.config.n_pages)):
            self.config.page = page
            self.load_niigrid()
            self.update_image()
            self.page_label.value = f'{page + 1}/{self.config.n_pages}'

    def save_image_or_gif(self, change):
        if change.new.endswith(';'):
            filepath = change.new[:-1]
            gif = filepath.endswith('.gif')
            config_dict = self.config.to_dict(grid_kwargs_only=True)
            if '/*.' in filepath:
                out_dir = filepath.split('/*.')[0]
                save_images_or_gifs(self.config.filepaths, out_dir, gif, self.config.max_samples, **config_dict)
            else:
                if gif:
                    save_gif(self.niigrid, filepath, **config_dict)
                else:
                    self.niigrid.get_image(**config_dict).save(filepath)

    def set_layout(self, change):
        self.layout_entry.value = LAYOUT_STRINGS[change.new]
        self.update_config(change, 'layout')

    def set_max_samples(self, change):
        self.config.max_samples = change.new
        self.config.nrows = None
        self.load_niigrid()
        self.update_image()

    def set_cmap(self, change, is_mask=False):
        if is_mask:
            self.cmap_mask_entry.value = change.new
        else:
            self.cmap_entry.value = change.new
        self.update_config(change, 'cmap', is_mask=is_mask)

    def set_resizing(self, change, is_mask=False):
        self.update_config(change, 'resizing', RESIZINGS.index(change.new), is_mask=is_mask)

    def set_cbar(self, change):
        self.config.cbar_vertical = change.new == 'vertical'
        self.update_config(change, 'cbar', change.new != '')

    def set_cbar_ticks(self, change):
        entry = change.new
        if ':' in entry:
            ticks = {float(s.split(':')[0]): s.split(':')[1] for s in entry.split('|')}
        elif not entry:
            ticks = []
        else:
            ticks = [float(s) for s in entry.split('|')]
        self.update_config(change, 'cbar_ticks', ticks)

    def update_origin(self, change, plane='sagittal'):
        self.config.origin[PLANES_4D.index(plane)] = change.new
        self.update_image()

    def update_config(self, change, attribute, value=None, is_mask=False, switch=False):
        value = change.new if value is None else value
        if attribute in ['alpha', 'cbar_x', 'cbar_y', 'cbar_width', 'cbar_length']:
            value *= .01
        if attribute.startswith('transp'):
            value = None if value == '' else value
        if attribute in LAYER_ATTRIBUTES:
            self.config.set_layer_attribute(attribute, value, is_mask)
        else:
            setattr(self.config, attribute, not getattr(self.config, attribute) if switch else value)
        self.update_image()

    def update_image(self):
        config_dict = self.config.to_dict(grid_kwargs_only=True)
        self.image = self.niigrid.get_image(**config_dict)
        self.image_widget.value = get_png_buffer(self.image)

        page = min(self.config.page, self.config.n_pages - 1)
        self.page_label.value = f'{page + 1}/{self.config.n_pages}'
        self.nrows_spinbox.value = self.niigrid.shape[0]
        nimage = self.niigrid.niis[0]
        self.vrange_start_spinbox.value = nimage.cmaps[0].vrange[0]
        self.vrange_stop_spinbox.value = nimage.cmaps[0].vrange[-1]
        if self.config.n_layers > 1:
            self.vrange_start_mask_spinbox.value = nimage.cmaps[-1].vrange[0]
            self.vrange_stop_mask_spinbox.value = nimage.cmaps[-1].vrange[-1]


def labelleft_checkbox(description, **kwargs):
    return HBox([Label(description), Checkbox(indent=False, **kwargs)])

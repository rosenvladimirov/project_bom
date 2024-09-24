try:
    import wx
except ValueError:
    pass
from ..dialog import SettingsDialog
from .ibom import main

def run_with_dialog(parser, config, logger):
    # type: (EcadParser, Config, Logger) -> None
    def save_config(dialog_panel, locally=False):
        config.set_from_dialog(dialog_panel)
        config.save(locally)

    config.load_from_ini()
    dlg = SettingsDialog(extra_data_func=parser.parse_extra_data,
                         extra_data_wildcard=parser.extra_data_file_filter(),
                         config_save_func=save_config,
                         file_name_format_hint=config.FILE_NAME_FORMAT_HINT,
                         version=config.version)
    try:
        config.netlist_initial_directory = os.path.dirname(parser.file_name)
        extra_data_file = parser.latest_extra_data(
            extra_dirs=[config.bom_dest_dir])
        if extra_data_file is not None:
            dlg.set_extra_data_path(extra_data_file)
        config.transfer_to_dialog(dlg.panel)
        if dlg.ShowModal() == wx.ID_OK:
            config.set_from_dialog(dlg.panel)
            main(parser, config, logger)
    finally:
        dlg.Destroy()

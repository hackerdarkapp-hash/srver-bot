from .db import (
    init_db,
    get_button, get_children, get_top_level_buttons,
    get_all_buttons_flat,
    get_response,
    save_user, get_user, get_all_users, get_users_count, get_all_active_user_ids,
    get_new_users_today, get_users_with_phone, save_phone, has_phone, toggle_block,
    get_setting, set_setting,
    seed_default_tools, button_exists_by_tool_id, seed_from_file,
    log_tool_usage, get_tool_stats,
)
from .db import (
    add_button      as _add_button,
    update_button   as _update_button,
    delete_button   as _delete_button,
    toggle_button   as _toggle_button,
    reorder_buttons as _reorder_buttons,
    set_response    as _set_response,
    delete_response as _delete_response,
)
from .backup import schedule_backup


def add_button(*args, **kwargs):
    result = _add_button(*args, **kwargs)
    schedule_backup()
    return result


def update_button(*args, **kwargs):
    result = _update_button(*args, **kwargs)
    schedule_backup()
    return result


def delete_button(*args, **kwargs):
    result = _delete_button(*args, **kwargs)
    schedule_backup()
    return result


def toggle_button(*args, **kwargs):
    result = _toggle_button(*args, **kwargs)
    schedule_backup()
    return result


def reorder_buttons(*args, **kwargs):
    result = _reorder_buttons(*args, **kwargs)
    schedule_backup()
    return result


def set_response(*args, **kwargs):
    _set_response(*args, **kwargs)
    schedule_backup()


def delete_response(*args, **kwargs):
    _delete_response(*args, **kwargs)
    schedule_backup()

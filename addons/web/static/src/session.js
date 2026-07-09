export const session = nwos.__session_info__ || {};
session.view_info ||= {};
delete nwos.__session_info__;

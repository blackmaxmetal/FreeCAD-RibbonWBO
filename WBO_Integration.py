# -*- coding: utf-8 -*-
# WBO_Integration.py - Isolated Workbench Organizer / Ribbon Integration Management
# PART 1: Imports, Configuration Loading, and Tab Filtering Logic

import os
import json
import FreeCAD
import FreeCADGui

try:
    from PySide import QtWidgets, QtCore
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore
    except ImportError:
        from PySide6 import QtWidgets, QtCore

def load_wbo_config():
    """
    Loads configuration data from GroupWorkbenches.json and name mappings from WB_Rename.json.
    Returns:
        groups_dict (dict): Group name -> list of internal WB names.
        single_wbs (list): List of internal WB names to show standalone.
        name_map (dict): Internal WB name -> {"native": str, "wbo": str}
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "GroupWorkbenches.json")
    rename_path = os.path.join(current_dir, "WB_Rename.json")

    groups_dict = {}
    single_wbs = []
    name_map = {}

    # 1. FALLBACK ENGINE PER WB_Rename.json
    if not os.path.exists(rename_path):
        try:
            default_rename = [
                ["PartDesignWorkbench", "Part Design", "Feature Design"],
                ["SketcherWorkbench", "Sketcher", "Sketching"],
                ["PartWorkbench", "Part", "CSG Design"],
                ["DraftWorkbench", "Draft", "Drafting"],
                ["BIMWorkbench", "BIM", "Architecture Design"]
            ]
            with open(rename_path, "w", encoding="utf-8") as f:
                json.dump(default_rename, f, indent=4, ensure_ascii=False)
            print(f"WBO-Ribbon: {rename_path} not found. Created a fallback layout template.")
        except Exception as err:
            print(f"WBO-Ribbon: Failed to write default rename JSON: {err}")

    # Caricamento e indicizzazione di WB_Rename.json
    if os.path.exists(rename_path):
        try:
            with open(rename_path, "r", encoding="utf-8") as f:
                rename_list = json.load(f)
                for item in rename_list:
                    if isinstance(item, list) and len(item) >= 3:
                        internal_name = str(item[0]).strip()
                        name_map[internal_name] = {
                            "native": str(item[1]).strip(),
                            "wbo": str(item[2]).strip()
                        }
        except Exception as e:
            print(f"WBO-Ribbon: Error reading WB_Rename.json: {e}")

    # 2. FALLBACK ENGINE PER GroupWorkbenches.json
    if not os.path.exists(json_path):
        try:
            default_config = {
                "WBO All": [],
                "Modeling": ["PartDesignWorkbench", "PartWorkbench", "SketcherWorkbench"],
                "Drafting & BIM": ["DraftWorkbench", "BIMWorkbench"],
                "WBO In Groups Dropdown": ["PartDesignWorkbench", "SketcherWorkbench"]
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print(f"WBO-Ribbon: {json_path} not found. Created a fallback group template.")
        except Exception as create_err:
            print(f"WBO-Ribbon: Failed to write default fallback JSON: {create_err}")

    # Caricamento effettivo di GroupWorkbenches.json
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                groups_dict = json.load(f)
                for g_name in list(groups_dict.keys()):
                    if not isinstance(groups_dict[g_name], list):
                        groups_dict[g_name] = []
        except Exception as e:
            print(f"WBO-Ribbon: Error reading Groups JSON: {e}")

    # Estrazione dei singoli workbench
    if "WBO In Groups Dropdown" in groups_dict:
        single_wbs = [wb for wb in groups_dict["WBO In Groups Dropdown"] if wb and not wb.startswith("-")]
        del groups_dict["WBO In Groups Dropdown"]

    return groups_dict, single_wbs, name_map

def run_tab_filtering(modern_menu_instance, target_group, groups_dict, name_map, wbo_enabled=True):
    """
    Visually filters and renames the Ribbon tabs based on the active group and name_map rules.
    Safely bypasses renames for active editing workbenches (like Sketcher) to prevent empty panels.
    """
    # Check if FreeCAD is currently inside an active Task Panel or Sketch Editing session
    is_freecad_editing = False
    try:
        if hasattr(FreeCADGui, "Control") and FreeCADGui.Control.isEditing():
            is_freecad_editing = True
    except Exception:
        pass

    # 1. Determine the allowed internal workbench names for filtering
    allowed_cleaned = []
    if wbo_enabled and target_group in groups_dict and not is_freecad_editing:
        is_all = (target_group == "WBO All")
        allowed_wbs = groups_dict[target_group]
        for wb in allowed_wbs:
            w_str = str(wb).strip().lower().replace(" ", "")
            if w_str.endswith("workbench"):
                w_str = w_str[:-9]
            if w_str and not w_str.startswith("-"):
                allowed_cleaned.append(w_str)
    else:
        is_all = True # Force show all if WBO is disabled or if FreeCAD is editing a sketch

    # 2. Get registered category widgets from the Ribbon UI instance
    categories = {}
    if hasattr(modern_menu_instance, "_categories") and isinstance(modern_menu_instance._categories, dict):
        categories = modern_menu_instance._categories

    # 3. Locate all underlying graphical QTabBars in the Ribbon layout tree
    tab_bar_targets = []
    if hasattr(modern_menu_instance, "ribbonTabBar"):
        try:
            r_bar = modern_menu_instance.ribbonTabBar()
            if r_bar:
                tab_bar_targets.append(r_bar)
        except Exception:
            pass

    for child_bar in modern_menu_instance.findChildren(QtWidgets.QTabBar):
        if child_bar not in tab_bar_targets:
            tab_bar_targets.append(child_bar)

    # Track only native structural keys to prevent cross-contamination during visibility loops
    native_categories_keys = [k for k in categories.keys() if k.endswith("Workspace") or k.endswith("Workbench") or k.replace(" ", "").islower()]

    # Detect the current active core workbench name from FreeCAD Gui
    active_wb_core = ""
    active_wb_clean = ""
    try:
        active_wb_core = FreeCADGui.activeWorkbench().name()
        active_wb_clean = active_wb_core.lower().replace(" ", "")
        if active_wb_clean.endswith("workbench"):
            active_wb_clean = active_wb_clean[:-9]
    except Exception:
        pass

    # 4. Scan and dynamically rename individual graphical Tab headers
    for tab_bar in tab_bar_targets:
        tab_colors_map = getattr(tab_bar, "_tabColors", None)

        for i in range(tab_bar.count()):
            current_tab_text = tab_bar.tabText(i).strip()
            matched_internal_wb = None

            # Cross-reference via name_map dictionary rows
            for internal_name, mapping in name_map.items():
                if current_tab_text in [mapping["native"], mapping["wbo"]]:
                    matched_internal_wb = internal_name
                    break

            # Fallback Lookup via active native Ribbon category keys
            if not matched_internal_wb:
                clean_tab_lookup = current_tab_text.lower().replace(" ", "")
                if clean_tab_lookup.endswith("workbench"):
                    clean_tab_lookup = clean_tab_lookup[:-9]

                for internal_name in native_categories_keys:
                    c_name = str(internal_name).strip().lower().replace(" ", "")
                    if c_name.endswith("workbench"):
                        c_name = c_name[:-9]
                    if c_name == clean_tab_lookup:
                        matched_internal_wb = internal_name
                        break

            # 5. Apply target translation string and safely inject pointer links
            if matched_internal_wb:
                native_name = name_map.get(matched_internal_wb, {}).get("native", current_tab_text)
                wbo_name = name_map.get(matched_internal_wb, {}).get("wbo", current_tab_text)

                # SPECIAL SUSPENSION: If we are editing a sketch, force native name for the active editing workbench
                if wbo_enabled and not (is_freecad_editing and matched_internal_wb == active_wb_core):
                    new_label = wbo_name

                    # Map the third column text inside the core workbench mapping (Fix line 3424)
                    if hasattr(modern_menu_instance, "wbNameMapping") and isinstance(modern_menu_instance.wbNameMapping, dict):
                        if native_name in modern_menu_instance.wbNameMapping:
                            modern_menu_instance.wbNameMapping[wbo_name] = modern_menu_instance.wbNameMapping[native_name]
                        elif matched_internal_wb in modern_menu_instance.wbNameMapping:
                            modern_menu_instance.wbNameMapping[wbo_name] = modern_menu_instance.wbNameMapping[matched_internal_wb]

                    # Map 3rd column string to real RibbonCategory widget pointer safely (Fix line 636)
                    if wbo_name not in categories:
                        if native_name in categories:
                            categories[wbo_name] = categories[native_name]
                        elif matched_internal_wb in categories:
                            categories[wbo_name] = categories[matched_internal_wb]
                else:
                    new_label = native_name

                # Safeguard tab color dictionary from KeyError crashes (Fix line 97)
                if tab_colors_map is not None and not isinstance(tab_colors_map, type(None)):
                    if native_name in tab_colors_map and wbo_name not in tab_colors_map:
                        tab_colors_map[wbo_name] = tab_colors_map[native_name]
                    elif wbo_name not in tab_colors_map:
                        tab_colors_map[wbo_name] = "#000000"

                if tab_bar.tabText(i) != new_label:
                    tab_bar.setTabText(i, new_label)
            else:
                matched_internal_wb = current_tab_text

            # 6. Apply visibility filtering to the QTabBar element
            w_clean = str(matched_internal_wb).strip().lower().replace(" ", "")
            if w_clean.endswith("workbench"):
                w_clean = w_clean[:-9]

            tab_should_be_visible = is_all or (w_clean in allowed_cleaned)

            # FORCE VISIBILITY FOR ACTIVE JUMPS
            if is_freecad_editing and active_wb_clean and w_clean == active_wb_clean:
                tab_should_be_visible = True

            if hasattr(tab_bar, "setTabVisible"):
                try:
                    tab_bar.setTabVisible(i, tab_should_be_visible)
                except Exception:
                    pass

        tab_bar.update()

    # 7. CRITICAL VISIBILITY FIX FOR CATEGORIES & PANELS
    for internal_name in native_categories_keys:
        category_widget = categories.get(internal_name)
        if not category_widget:
            continue

        w_clean = str(internal_name).strip().lower().replace(" ", "")
        if w_clean.endswith("workbench"):
            w_clean = w_clean[:-9]

        should_be_visible = is_all or (w_clean in allowed_cleaned)

        if is_freecad_editing and active_wb_clean and w_clean == active_wb_clean:
            should_be_visible = True

        if hasattr(category_widget, "setVisible"):
            category_widget.setVisible(should_be_visible)

        if hasattr(category_widget, "toggleViewAction"):
            action = category_widget.toggleViewAction()
            if action and hasattr(action, "setVisible"):
                action.setVisible(should_be_visible)

    if hasattr(modern_menu_instance, "update"):
        modern_menu_instance.update()

# PART 2: Dropdown Initialization, OpenTheme CSS Styling, and Layout Anchoring

def apply_wbo_ribbon_patch(modern_menu_instance):
    """Main entry point triggered by Ribbon UI interaction signals."""
    # ABSOLUTE SAFEGUARD: If WBO is globally disabled, abort filtering and ensure native reset
    p_ribbon = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Ribbon")
    if not p_ribbon.GetBool("EnableWBOIntegration", True):
        if hasattr(modern_menu_instance, "_wbo_dropdown_widget") and modern_menu_instance._wbo_dropdown_widget:
            modern_menu_instance._wbo_dropdown_widget.setEnabled(False)
            modern_menu_instance._wbo_dropdown_widget.hide()
        return

    # 1. Load group configurations and the three-column rename map
    groups_dict, single_wbs, name_map = load_wbo_config()

    all_tabs = []
    if hasattr(modern_menu_instance, "_categories") and isinstance(modern_menu_instance._categories, dict):
        all_tabs = list(modern_menu_instance._categories.keys())
    groups_dict["WBO All"] = all_tabs

    groups_list = [g for g in groups_dict.keys() if not (g.startswith("WBO ") and g != "WBO All")]

    p_global = FreeCAD.ParamGet("User parameter:BaseApp/WB_Organizer")
    current_group = p_global.GetString("SelectedGroup", "").strip()

    if not current_group or (current_group not in groups_list and current_group not in single_wbs):
        user_defined_groups = [g for g in groups_list if g != "WBO All"]
        current_group = user_defined_groups if user_defined_groups else ("WBO All" if "WBO All" in groups_list else "")

    wbo_dropdown = getattr(modern_menu_instance, "_wbo_dropdown_widget", None)
    if not wbo_dropdown:
        wbo_dropdown = QtWidgets.QComboBox()
        wbo_dropdown.setFixedWidth(180)
        wbo_dropdown.setMinimumHeight(24)
        wbo_dropdown.setToolTip("Select WBO Group or Workbench")

        # Extract dynamic colors from Qt Application palette
        palette = QtWidgets.QApplication.palette()
        try:
            text_color = palette.color(palette.ColorRole.WindowText).name()
            bg_color = palette.color(palette.ColorRole.Button).name()
            list_bg_color = palette.color(palette.ColorRole.Base).name()
            highlight_color = palette.color(palette.ColorRole.Highlight).name()
            highlight_text = palette.color(palette.ColorRole.HighlightedText).name()
            border_color = palette.color(palette.ColorRole.Mid).name()
        except AttributeError:
            text_color = palette.color(palette.WindowText).name()
            bg_color = palette.color(palette.Button).name()
            list_bg_color = palette.color(palette.Base).name()
            highlight_color = palette.color(palette.Highlight).name()
            highlight_text = palette.color(palette.HighlightedText).name()
            border_color = palette.color(palette.Mid).name()

        if border_color == "#000000" or border_color == bg_color:
            border_color = "#555555" if palette.color(palette.Window).lightness() < 128 else "#cccccc"

        wbo_dropdown.setStyleSheet(f"""
            QComboBox {{ font-weight: bold; color: {text_color}; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 4px; padding: 2px 24px 2px 8px; }}
            QComboBox:hover {{ background-color: {list_bg_color}; border: 1px solid {highlight_color}; }}
            QComboBox:on {{ background-color: {list_bg_color}; }}
            QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 20px; border-left-width: 0px; }}
            QComboBox QAbstractItemView {{ color: {text_color}; background-color: {list_bg_color}; border: 1px solid {border_color}; selection-background-color: {highlight_color}; selection-color: {highlight_text}; padding: 4px; }}
            QComboBox QAbstractItemView::separator {{ height: 1px; background-color: {border_color}; margin-top: 4px; margin-bottom: 4px; }}
        """)
        modern_menu_instance._wbo_dropdown_widget = wbo_dropdown

    # 2. Block signals temporarily to prevent unwanted execution while rebuilding items
    wbo_dropdown.blockSignals(True)
    wbo_dropdown.clear()

    # Populate standalone workbenches renamed using the 3rd column (wbo)
    for wb in single_wbs:
        display_name = name_map.get(wb, {}).get("wbo", wb)
        # Strip trailing 'Workbench' suffix for clean look if mapped
        if display_name.endswith("Workbench") and wb in name_map:
            display_name = display_name[:-9]
        wbo_dropdown.addItem(display_name, wb)

    # Insert a clear separating line between standalone WBs and main groups
    if single_wbs and groups_list:
        wbo_dropdown.insertSeparator(wbo_dropdown.count())

    # Populate the primary defined WBO groups
    for group in groups_list:
        wbo_dropdown.addItem(group, group)

    # Restore the index pointing to the user's last selected active group
    idx = wbo_dropdown.findData(current_group)
    if idx >= 0:
        wbo_dropdown.setCurrentIndex(idx)
    wbo_dropdown.blockSignals(False)

    # SECURE CHECK: Only disconnect if there are active connected slots/receivers
    try:
        # Check receivers for the specific signal signature
        if wbo_dropdown.receivers(QtCore.SIGNAL("currentIndexChanged(int)")) > 0:
            wbo_dropdown.currentIndexChanged.disconnect()
    except (RuntimeError, TypeError, Exception):
        # Secondary fallback safeguard
        try:
            wbo_dropdown.currentIndexChanged.disconnect()
        except Exception:
            pass

    def on_dropdown_group_changed(index):
        real_name = wbo_dropdown.itemData(index)
        if not real_name:
            return

        # Persist the state in FreeCAD user parameters
        FreeCAD.ParamGet("User parameter:BaseApp/WB_Organizer").SetString("SelectedGroup", real_name)

        # Helper function to focus a ribbon tab by its expected visual 3rd-column text
        def force_tab_activation_by_text(target_label_text):
            tab_bar_targets = []
            if hasattr(modern_menu_instance, "ribbonTabBar"):
                try:
                    r_bar = modern_menu_instance.ribbonTabBar()
                    if r_bar:
                        tab_bar_targets.append(r_bar)
                except Exception:
                    pass
            for child_bar in modern_menu_instance.findChildren(QtWidgets.QTabBar):
                if child_bar not in tab_bar_targets:
                    tab_bar_targets.append(child_bar)

            # Look up the tab index matching the WBO 3rd-column label
            for tab_bar in tab_bar_targets:
                for idx in range(tab_bar.count()):
                    if tab_bar.tabText(idx).strip() == target_label_text.strip():
                        # Programmatically switch index to bypass pyqtribbon strict ValueError validations
                        tab_bar.setCurrentIndex(idx)
                        tab_bar.update()
                        return True
            return False

        # Direct activation if a real single workbench is chosen
        if real_name in single_wbs:
            try:
                FreeCADGui.activateWorkbench(real_name)
                def delay_single_focus():
                    wbo_name = name_map.get(real_name, {}).get("wbo", real_name)
                    force_tab_activation_by_text(wbo_name)
                QtCore.QTimer.singleShot(25, delay_single_focus)
            except Exception as e:
                print(f"[WBO-RIBBON] Error activating single workbench {real_name}: {e}")
            return

        # Enable global recursion protection flag inherited by ModernMenu class
        setattr(modern_menu_instance.__class__, "_wbo_patch_running", True)

        try:
            # Filter and apply the 3rd column (wbo) names across the Ribbon layout
            run_tab_filtering(modern_menu_instance, real_name, groups_dict, name_map, wbo_enabled=True)

            try:
                import WBO_Gui
                WBO_Gui.onWorkbenchActivated()
            except Exception:
                pass

            # Identify the first valid workbench belonging to the group
            if real_name in groups_dict:
                group_workbenches = groups_dict[real_name]
                first_valid_wb = None

                for wb in group_workbenches:
                    wb_str = str(wb).strip()
                    if not wb_str or wb_str.startswith("-") or wb_str.startswith("---"):
                        continue
                    if "WBO Disabled" in groups_dict and wb_str in groups_dict["WBO Disabled"]:
                        continue
                    first_valid_wb = wb_str
                    break

                # Trigger immediate activation of the first workbench
                if first_valid_wb:
                    available_wbs = FreeCADGui.listWorkbenches()
                    target_wb = None

                    # Suffix resolution and matching handling
                    if first_valid_wb in available_wbs:
                        target_wb = first_valid_wb
                    elif first_valid_wb.endswith("Workbench") and first_valid_wb[:-9] in available_wbs:
                        target_wb = first_valid_wb[:-9]
                    elif not first_valid_wb.endswith("Workbench") and f"{first_valid_wb}Workbench" in available_wbs:
                        target_wb = f"{first_valid_wb}Workbench"

                    if target_wb:
                        try:
                            # 1. Activate the core workbench inside FreeCAD architecture
                            FreeCADGui.activateWorkbench(target_wb)

                            # 2. FIXED TAB FOCUS VIA QTABBAR INDEX SETTING: Bypass pyqtribbon validation completely
                            def delay_group_first_focus():
                                wbo_label = name_map.get(target_wb, {}).get("wbo", target_wb)
                                # If direct 3rd-column label lookup fails, fallback to native name string
                                if not force_tab_activation_by_text(wbo_label):
                                    native_label = name_map.get(target_wb, {}).get("native", target_wb)
                                    force_tab_activation_by_text(native_label)

                            # Execute 35ms later to guarantee pyqtribbon layout cycle has fully stabilized
                            QtCore.QTimer.singleShot(35, delay_group_first_focus)
                        except Exception as e:
                            print(f"[WBO-Ribbon] Error activating {target_wb}: {e}")
        finally:
            # Release loop protection flag for future manual tab switches
            setattr(modern_menu_instance.__class__, "_wbo_patch_running", False)

    wbo_dropdown.currentIndexChanged.connect(on_dropdown_group_changed)

    # ==============================================================================
    # STRUCTURED GEOMETRY INJECTION VIA NATIVE PYQTRIBBON METHODS - FIXED FOR RE-SHOW
    # ==============================================================================
    # Ensure the widget is visible, enabled, and attached to the correct active layout toolbar
    wbo_dropdown.setEnabled(True)
    wbo_dropdown.show()

    if hasattr(modern_menu_instance, "rightToolBar") and hasattr(modern_menu_instance.rightToolBar(), "addWidget"):
        try:
            # If the widget parent changed or was detached by Qt, re-add it to the toolbar layout
            right_tb = modern_menu_instance.rightToolBar()
            if wbo_dropdown.parent() != right_tb:
                right_tb.addWidget(wbo_dropdown)
            wbo_dropdown.show()
        except Exception as e:
            print(f"[WBO-Ribbon] rightToolBar.addWidget failed: {e}")
    else:
        mw = FreeCADGui.getMainWindow()
        status_bar = mw.statusBar() if mw else None
        if status_bar and wbo_dropdown.parent() != status_bar:
            status_bar.addPermanentWidget(wbo_dropdown)
            wbo_dropdown.show()

    # Apply initial filter configuration immediately on startup
    if current_group not in single_wbs:
        run_tab_filtering(modern_menu_instance, current_group, groups_dict, name_map, wbo_enabled=True)

def inject_wbo_switch(modern_menu_instance):
    """Injects the custom WBO toggle switch into the Ribbon's Main Menu - Section 4A."""
    # 1. Locate the primary Main Menu instance within the Ribbon structure
    main_menu = modern_menu_instance if isinstance(modern_menu_instance, QtWidgets.QMenu) else None
    if not main_menu and hasattr(modern_menu_instance, "settingsMenu"):
        main_menu = modern_menu_instance.settingsMenu.parent() if hasattr(modern_menu_instance.settingsMenu, "parent") else None
    if not main_menu:
        for child_menu in modern_menu_instance.findChildren(QtWidgets.QMenu):
            if child_menu.parent() == modern_menu_instance:
                main_menu = child_menu
                break
    if not main_menu:
        return

    # Prevent duplicate switch action instantiations
    for act in main_menu.actions():
        if act.objectName() == "action_main_switch_wbo_integration":
            return

    # 2. Fetch current activation state from FreeCAD preferences
    p_ribbon = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Ribbon")
    wbo_enabled = p_ribbon.GetBool("EnableWBOIntegration", True)

    wbo_widget_action = QtWidgets.QWidgetAction(main_menu)
    wbo_widget_action.setObjectName("action_main_switch_wbo_integration")

    # 3. Construct the container widget layout for the menu item
    container = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(container)
    layout.setContentsMargins(12, 6, 12, 6)
    layout.setSpacing(15)

    label = QtWidgets.QLabel("Enable Workbench Organizer (WBO)")
    switch_btn = QtWidgets.QPushButton()
    switch_btn.setObjectName("wbo_main_switch_button")
    switch_btn.setCheckable(True)
    switch_btn.setChecked(wbo_enabled)
    switch_btn.setFixedWidth(54)
    if hasattr(switch_btn, "setFixedHeight"):
        switch_btn.setFixedHeight(22)

    # Extract dynamic colors from Qt Application palette for responsive styling
    palette = QtWidgets.QApplication.palette()
    bg_color = palette.color(palette.ColorRole.Button).name()
    highlight_color = palette.color(palette.ColorRole.Highlight).name()
    text_color = palette.color(palette.ColorRole.WindowText).name()

    switch_btn.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {bg_color};
            border: 1px solid #777777;
            border-radius: 11px;
            text-align: left;
            padding-left: 6px;
            font-weight: bold;
            font-size: 10px;
            color: {text_color};
        }}
        QPushButton:checked {{
            background-color: {highlight_color};
            border-color: {highlight_color};
            text-align: right;
            padding-right: 6px;
            color: white;
        }}
        """
    )

    switch_btn.setText("ON" if wbo_enabled else "OFF")


    # switch_btn.setStyleSheet(f"""
    #     QPushButton {{ background-color: {bg_color}; border: 1px solid #777777; border-radius: 11px; text-align: left; padding-left: 6px; font-weight: bold; font-size: 10px; color: {text_color}; }}
    #     QPushButton:checked {{ background-color: {highlight_color}; text-align: right; padding-right: 6px; color: white; border-color: {highlight_color}; }}
    # """)
    # switch_btn.setText("ON" if wbo_enabled else "OFF")

    def on_switch_toggled(checked):
        p_ribb = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Ribbon")
        p_ribb.SetBool("EnableWBOIntegration", checked)
        switch_btn.setText("ON" if checked else "OFF")

        g_dict, s_wbs, n_map = load_wbo_config()

        if checked:
            # Re-apply patch to reconstruct or sync configurations
            apply_wbo_ribbon_patch(modern_menu_instance)

            # CRITICAL FIX: Ensure the dropdown is enabled, visible, and cleared of disabled styles
            if hasattr(modern_menu_instance, "_wbo_dropdown_widget") and modern_menu_instance._wbo_dropdown_widget:
                modern_menu_instance._wbo_dropdown_widget.setEnabled(True)

                # Restore dynamic palette styling to clear the temporary grey disabled stylesheet
                palette = QtWidgets.QApplication.palette()
                try:
                    text_color = palette.color(palette.ColorRole.WindowText).name()
                    bg_color = palette.color(palette.ColorRole.Button).name()
                    border_color = palette.color(palette.ColorRole.Mid).name()
                except AttributeError:
                    text_color = palette.color(palette.WindowText).name()
                    bg_color = palette.color(palette.Button).name()
                    border_color = palette.color(palette.Mid).name()

                modern_menu_instance._wbo_dropdown_widget.setStyleSheet(f"""
                    QComboBox {{ font-weight: bold; color: {text_color}; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 4px; padding: 2px 24px 2px 8px; }}
                """)
                modern_menu_instance._wbo_dropdown_widget.show()

                current_idx = modern_menu_instance._wbo_dropdown_widget.currentIndex()
                if current_idx >= 0:
                    modern_menu_instance._wbo_dropdown_widget.currentIndexChanged.emit(current_idx)
        else:
            # Securely disable and hide the custom WBO dropdown widget
            if hasattr(modern_menu_instance, "_wbo_dropdown_widget") and modern_menu_instance._wbo_dropdown_widget:
                modern_menu_instance._wbo_dropdown_widget.setEnabled(False)
                modern_menu_instance._wbo_dropdown_widget.setStyleSheet(
                    modern_menu_instance._wbo_dropdown_widget.styleSheet() + """
                    QComboBox:disabled { color: #888888; background-color: #555555; border: 1px solid #444444; }
                    """
                )
                modern_menu_instance._wbo_dropdown_widget.hide()

            # RESET VIA NATIVE CATEGORIES: Reset only using real initialized keys to prevent startup conflicts
            real_all_tabs = []
            if hasattr(modern_menu_instance, "_categories") and isinstance(modern_menu_instance._categories, dict):
                real_all_tabs = list(modern_menu_instance._categories.keys())

            reset_groups = {"WBO All": real_all_tabs}
            run_tab_filtering(modern_menu_instance, "WBO All", reset_groups, n_map, wbo_enabled=False)

        def force_layout_refresh():
            try:
                for child_bar in modern_menu_instance.findChildren(QtWidgets.QTabBar):
                    child_bar.update()
                    if hasattr(child_bar, "adjustSize"):
                        child_bar.adjustSize()
                modern_menu_instance.update()
            except Exception:
                pass

        QtCore.QTimer.singleShot(30, force_layout_refresh)

    # Connect toggle signal and assemble the widget layout elements into the main menu
    switch_btn.toggled.connect(on_switch_toggled)
    layout.addWidget(label)
    layout.addStretch()
    layout.addWidget(switch_btn)
    container.setLayout(layout)
    wbo_widget_action.setDefaultWidget(container)

    main_menu.addSeparator()
    main_menu.addAction(wbo_widget_action)

def setup_async_startup(modern_menu_instance, modern_menu_class):
    """Handles the asynchronous startup synchronization for WBO and Native UI elements."""
    def delayed_startup():
        try:
            # 1. Look for and inject FreeCAD's native workbench selector into the status bar
            inject_native_workbench_selector_to_statusbar()

            # 2. Extract configuration data and name map for the initialization sequence
            groups_dict, single_wbs, name_map = load_wbo_config()

            p_ribbon = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Ribbon")
            if not p_ribbon.GetBool("EnableWBOIntegration", True):
                print("WBO Integration is currently disabled via Ribbon UI preferences.")

                # If disabled on startup, explicitly enforce invisibility and disable the dropdown widget
                if hasattr(modern_menu_instance, "_wbo_dropdown_widget") and modern_menu_instance._wbo_dropdown_widget:
                    modern_menu_instance._wbo_dropdown_widget.setEnabled(False)
                    modern_menu_instance._wbo_dropdown_widget.hide()

                # SECURE FULL RECOVERY AT COLD START: Extract every single ribbon tab currently loaded in Qt TabBar
                real_all_tabs = []
                tab_bar_targets = []
                if hasattr(modern_menu_instance, "ribbonTabBar"):
                    try:
                        r_bar = modern_menu_instance.ribbonTabBar()
                        if r_bar: tab_bar_targets.append(r_bar)
                    except Exception: pass
                for child_bar in modern_menu_instance.findChildren(QtWidgets.QTabBar):
                    if child_bar not in tab_bar_targets: tab_bar_targets.append(child_bar)

                # Scan the actual physical QTabBar headers to catch lazy loaded categories
                for t_bar in tab_bar_targets:
                    for i in range(t_bar.count()):
                        t_text = t_bar.tabText(i).strip()
                        if t_text and t_text not in real_all_tabs:
                            real_all_tabs.append(t_text)

                # Fallback merge from current active categories internal keys dictionary
                if hasattr(modern_menu_instance, "_categories") and isinstance(modern_menu_instance._categories, dict):
                    for k in modern_menu_instance._categories.keys():
                        if k not in real_all_tabs: real_all_tabs.append(k)

                # Force full visibility reset (wbo_enabled=False) using the composite tab database list
                reset_groups = {"WBO All": real_all_tabs}
                run_tab_filtering(modern_menu_instance, "WBO All", reset_groups, name_map, wbo_enabled=False)

                # Secondary safety pass: ensure all tabs inside tab bars are explicitly set to visible
                try:
                    for child_bar in tab_bar_targets:
                        for i in range(child_bar.count()):
                            if hasattr(child_bar, "setTabVisible"):
                                child_bar.setTabVisible(i, True)
                        child_bar.update()
                    modern_menu_instance.update()
                except Exception:
                    pass
                return

            # If WBO is active, execute the standard structural patch setup
            if getattr(modern_menu_class, "_wbo_patch_running", False):
                return

            setattr(modern_menu_class, "_wbo_patch_running", True)
            apply_wbo_ribbon_patch(modern_menu_instance)

            if hasattr(modern_menu_instance, "_wbo_dropdown_widget") and modern_menu_instance._wbo_dropdown_widget:
                current_idx = modern_menu_instance._wbo_dropdown_widget.currentIndex()
                if current_idx >= 0:
                    modern_menu_instance._wbo_dropdown_widget.currentIndexChanged.emit(current_idx)
        except Exception as e:
            print(f"[WBO-Bridge] Error during asynchronous initialization: {e}")
        finally:
            setattr(modern_menu_class, "_wbo_patch_running", False)

    # 350ms ensures that the core UI thread finishes constructing standard components before filtering runs
    QtCore.QTimer.singleShot(350, delayed_startup)

def inject_native_workbench_selector_to_statusbar():
    """Finds FreeCAD's native workbench selection combobox and moves it permanently into the Status Bar."""
    main_window = FreeCADGui.getMainWindow()
    if not main_window:
        return
    status_bar = main_window.statusBar()
    if not status_bar:
        return

    for child in status_bar.children():
        if child.objectName() == "native_wb_selector_container":
            return

    native_combo = None
    all_combos = main_window.findChildren(QtWidgets.QComboBox)
    for combo in all_combos:
        if combo.objectName() == "" and hasattr(combo, "toolTip") and "workbench" in combo.toolTip().lower():
            native_combo = combo
            break
        try:
            if "Workbench" in combo.metaObject().className() or "Wb" in combo.metaObject().className():
                native_combo = combo
                break
        except Exception:
            pass

    if not native_combo:
        for toolbar in main_window.findChildren(QtWidgets.QToolBar):
            if "workbench" in toolbar.objectName().lower() or "workbench" in toolbar.windowTitle().lower():
                found_combo = toolbar.findChild(QtWidgets.QComboBox)
                if found_combo:
                    native_combo = found_combo
                    break

    if native_combo:
        try:
            container = QtWidgets.QWidget()
            container.setObjectName("native_wb_selector_container")
            layout = QtWidgets.QHBoxLayout(container)
            layout.setContentsMargins(5, 0, 5, 0)
            layout.setSpacing(5)

            label = QtWidgets.QLabel("Active WB:")
            label.setStyleSheet("font-weight: bold; font-size: 10px;")

            native_combo.setFixedWidth(160)
            native_combo.setMinimumHeight(20)
            if hasattr(native_combo, "setFixedHeight"):
                native_combo.setFixedHeight(22)

            layout.addWidget(label)
            layout.addWidget(native_combo)
            container.setLayout(layout)

            status_bar.addPermanentWidget(container)
            container.show()
            native_combo.show()
        except Exception as e:
            print(f"[WBO-Ribbon] Failed to anchor native workbench selector: {e}")



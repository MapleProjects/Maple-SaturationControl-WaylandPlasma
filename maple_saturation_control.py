#!/usr/bin/env python3
import sys
import subprocess
import re
import os
import json
import shutil
import time
import xml.etree.ElementTree as ET
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QSlider, QDoubleSpinBox, QPushButton,
                             QGroupBox, QMessageBox, QStatusBar)
from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtGui import QIcon, QFont, QPalette, QColor

class DesignSystem:
    """
    Curated premium dark mode theme color tokens and stylesheets
    designed to deliver a high-end visual experience.
    """
    COLOR_BACKGROUND = "#0B0B14"  # Ultra deep indigo-slate
    COLOR_SURFACE = "#121225"     # Sleek navy-violet card background
    COLOR_PRIMARY = "#89B4FA"     # Pastel blue primary
    COLOR_ACCENT = "#CBA6F7"      # Pastel lavender accent
    COLOR_TEXT = "#CDD6F4"        # Off-white readability text
    COLOR_TEXT_DIM = "#7F849C"    # Slate grey for subtitles
    COLOR_SUCCESS = "#A6E3A1"     # Pastel green
    COLOR_DANGER = "#F38BA8"      # Soft pastel red
    COLOR_BORDER = "#23233B"      # Deep border highlight

    STYLESHEET = f"""
        QMainWindow {{
            background-color: {COLOR_BACKGROUND};
            color: {COLOR_TEXT};
        }}
        QWidget {{
            background-color: {COLOR_BACKGROUND};
            color: {COLOR_TEXT};
            font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
            font-size: 14px;
        }}
        QGroupBox {{
            border: 1px solid {COLOR_BORDER};
            border-radius: 12px;
            margin-top: 24px;
            background-color: {COLOR_SURFACE};
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 4px 14px;
            background-color: {COLOR_BACKGROUND}; 
            border-radius: 6px;
            color: {COLOR_ACCENT};
        }}
        QPushButton {{
            background-color: {COLOR_PRIMARY};
            color: {COLOR_BACKGROUND};
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {COLOR_ACCENT};
        }}
        QPushButton:pressed {{
            background-color: #B4BEFE;
        }}
        QSlider::groove:horizontal {{
            border: 1px solid {COLOR_BORDER};
            height: 6px;
            background: #11111B;
            margin: 2px 0;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {COLOR_PRIMARY};
            border: none;
            width: 18px;
            height: 18px;
            margin: -6px 0;
            border-radius: 9px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {COLOR_ACCENT};
        }}
        QComboBox {{
            background-color: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            color: {COLOR_TEXT};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QDoubleSpinBox {{
            background-color: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            color: {COLOR_TEXT};
        }}
    """

class SettingsManager:
    """
    Manages loading and saving of visual configuration settings.
    Saves profile parameters in a standard JSON format inside the user config home.
    """
    CONFIG_DIR = os.path.expanduser("~/.config/maple_saturation_control")
    CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

    @classmethod
    def load_settings(cls):
        if not os.path.exists(cls.CONFIG_FILE):
             return {'saturation': 1.0, 'gamma': 1.0}
        try:
            with open(cls.CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {'saturation': 1.0, 'gamma': 1.0}

    @classmethod
    def save_settings(cls, sat, gamma):
        os.makedirs(cls.CONFIG_DIR, exist_ok=True)
        try:
            with open(cls.CONFIG_FILE, 'w') as f:
                json.dump({'saturation': sat, 'gamma': gamma}, f)
        except Exception as e:
            print(f"Error saving settings: {e}")

class DisplayController:
    """
    Handles system interactions with colord and kscreen-doctor 
    to dynamically query, register, and apply modified color profiles.
    """
    @staticmethod
    def get_connected_displays():
        """
        Retrieves names of all active displays using native kscreen-doctor JSON parser.
        """
        displays = []
        try:
            result = subprocess.run(['kscreen-doctor', '-j'], capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            for output in data.get('outputs', []):
                if output.get('connected') and output.get('enabled'):
                    displays.append(output.get('name'))
        except Exception as e:
            print(f"Error retrieving displays via kscreen-doctor: {e}")
        return displays

    @staticmethod
    def ensure_colord_device(display_name):
        """
        Registers the display device in colord daemon if not already configured.
        This forces KWin to process color transformation matrices (CTM) in SDR.
        """
        try:
            res = subprocess.run(['colormgr', 'get-devices'], capture_output=True, text=True)
            if display_name in res.stdout:
                return True
            
            # Create a persistent user-level display device mapping in colord
            cmd = ['colormgr', 'create-device', display_name, 'normal', 'display']
            subprocess.run(cmd, check=True)
            return True
        except Exception as e:
            print(f"Error ensuring colord device mapping: {e}")
            return False

    @staticmethod
    def apply_profile_wayland(display, saturation, gamma):
        """
        Performs xyY primary gamut modifications and TRC curve shifts inside 
        an XML representation of sRGB, recompiles it to ICC, and loads it to the display.
        """
        # Ensure colord profile binding is active so KWin compiles the shader transformations
        DisplayController.ensure_colord_device(display)
        
        # 1. Resolve System Base Profile Path
        possible_paths = [
            "/usr/share/ghostscript/iccprofiles/srgb.icc",
            "/usr/share/color/icc/sRGB.icc",
            "/usr/share/color/icc/colord/sRGB.icc",
            "/usr/share/color/icc/colord/WideGamutRGB.icc"
        ]
        base_profile = None
        for path in possible_paths:
            if os.path.exists(path):
                base_profile = path
                break
                
        if not base_profile:
            return False, "Base sRGB profile not found in typical system paths."

        # 2. Verify existence of iccxml compiler tools
        icc_to_xml = shutil.which("iccToXml") or shutil.which("icc2xml")
        xml_to_icc = shutil.which("iccFromXml") or shutil.which("xml2icc")
        
        if not icc_to_xml or not xml_to_icc:
            return False, "iccxml compiler tools (iccToXml / iccFromXml) are missing."

        # 3. Configure Output File Paths
        temp_dir = os.path.expanduser("~/.local/share/icc")
        os.makedirs(temp_dir, exist_ok=True)
        xml_path = os.path.join(temp_dir, "temp_profile.xml")
        
        # Alternating fixed profile filenames to trigger KWin cache reloads
        # while keeping the directory clean and restricted to exactly two active files.
        icc_path_a = os.path.join(temp_dir, "maple_active_a.icc")
        icc_path_b = os.path.join(temp_dir, "maple_active_b.icc")
        
        mtime_a = os.path.getmtime(icc_path_a) if os.path.exists(icc_path_a) else 0
        mtime_b = os.path.getmtime(icc_path_b) if os.path.exists(icc_path_b) else 0
        
        if mtime_a > mtime_b:
            icc_path = icc_path_b
        else:
            icc_path = icc_path_a

        try:
            # 4. Decompile Base Profile to XML
            subprocess.run([icc_to_xml, base_profile, xml_path], check=True)

            target_sat = max(0.01, float(saturation))
            sat_factor = 1.0 / target_sat
            
            # Standard sRGB default TRC exponent is 2.2
            target_gamma_val = 2.2 / float(gamma)

            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # --- CHROMATICITY VECTOR SCALING (xyY Gamut Modification) ---
            def get_xyz(node):
                return float(node.attrib['X']), float(node.attrib['Y']), float(node.attrib['Z'])

            def xyz_to_xyy(X, Y, Z):
                s = X + Y + Z
                if s == 0: 
                    return 0.3127, 0.3290, Y  # D65 standard coordinates as safe fallback
                return X/s, Y/s, Y

            def xyy_to_xyz(x, y, Y):
                if y == 0: 
                    return 0.0, 0.0, 0.0
                X = (Y / y) * x
                Z = (Y / y) * (1.0 - x - y)
                return X, Y, Z
            
            tags_map = {}
            for param_tag in root.findall(".//XYZType"):
                sig = param_tag.find("TagSignature")
                xyz = param_tag.find("XYZNumber")
                if sig is not None and xyz is not None:
                    tags_map[sig.text] = xyz

            # D65 White Point mapping reference for SDR monitors
            white_x = 0.3127
            white_y = 0.3290
            
            # Per-primary weighting factor to avoid blue dominance and color clipping artifacts
            primary_weights = {
                'rXYZ': 1.0, 
                'gXYZ': 1.0, 
                'bXYZ': 0.1
            }

            if 'rXYZ' in tags_map and 'gXYZ' in tags_map and 'bXYZ' in tags_map:
                for prim in ['rXYZ', 'gXYZ', 'bXYZ']:
                    node = tags_map[prim]
                    old_X, old_Y, old_Z = get_xyz(node)
                    old_x, old_y, old_Y_lum = xyz_to_xyy(old_X, old_Y, old_Z)
                    
                    weight = primary_weights.get(prim, 1.0)
                    if target_sat > 1.0:
                        # Scaled chromaticity contraction for boosted saturation
                        effective_sat = 1.0 + (target_sat - 1.0) * weight
                        local_factor = 1.0 / effective_sat
                    else:
                        local_factor = sat_factor
                    
                    # Contract chromaticity vectors relative to neutral axis D65
                    new_x = white_x + (old_x - white_x) * local_factor
                    new_y = white_y + (old_y - white_y) * local_factor
                    
                    new_X, new_Y, new_Z = xyy_to_xyz(new_x, new_y, old_Y_lum)
                    
                    node.attrib['X'] = f"{new_X:.6f}"
                    node.attrib['Y'] = f"{new_Y:.6f}"
                    node.attrib['Z'] = f"{new_Z:.6f}"
            
            # --- TONE REPRODUCTION CURVE (TRC replacement) ---
            tags_node = root.find("Tags")
            if tags_node is None:
                tags_node = root
            
            # Wipe existing TRC tags to prevent definition conflicts
            for curve_node in tags_node.findall("curveType"):
                sigs = [s.text for s in curve_node.findall("TagSignature")]
                if 'rTRC' in sigs or 'gTRC' in sigs or 'bTRC' in sigs:
                    tags_node.remove(curve_node)
            
            # Inject a new 256-point Sampled LUT representing the curve Shift
            curve_node = ET.SubElement(tags_node, "curveType")
            ET.SubElement(curve_node, "TagSignature").text = "rTRC"
            ET.SubElement(curve_node, "TagSignature").text = "gTRC"
            ET.SubElement(curve_node, "TagSignature").text = "bTRC"
            
            exponent = 2.2 / float(gamma)
            lut_values = []
            for i in range(256):
                norm_x = i / 255.0
                norm_y = norm_x ** exponent
                val_int = int(norm_y * 65535.0 + 0.5)
                val_int = max(0, min(65535, val_int))
                lut_values.append(str(val_int))
            
            curve_node.text = "\n"  # Prepare formatting indentation
            ET.SubElement(curve_node, "Curve").text = " ".join(lut_values)
            
            # Force KWin to parse the profile as a physical display calibration device
            header = root.find("Header")
            if header is not None:
                device_class = header.find("ProfileDeviceClass")
                if device_class is not None:
                    device_class.text = "mntr"
            
            # Update Internal Descriptor metadata
            desc_tag_node = None
            for desc_type in ['textDescriptionType', 'textType', 'multiLocalizedUnicodeType']:
                for node in root.findall(f".//{desc_type}"):
                    sig = node.find("TagSignature")
                    if sig is not None and sig.text == 'desc':
                        desc_tag_node = node
                        break
                if desc_tag_node is not None: 
                    break

            if desc_tag_node is not None:
                 timestamp = int(time.time() * 1000)
                 new_desc = f"Sat{target_sat}_Gam{gamma}_{timestamp}"
                 for text_tag in ['ASCII', 'String', 'Unicode']:
                     t_node = desc_tag_node.find(text_tag)
                     if t_node is not None:
                          t_node.text = new_desc
            
            # Format XML with clean indentations
            def indent(elem, level=0):
                i = "\n" + level*"  "
                if len(elem):
                    if not elem.text or not elem.text.strip():
                        elem.text = i + "  "
                    if not elem.tail or not elem.tail.strip():
                        elem.tail = i
                    for elem in elem:
                        indent(elem, level+1)
                    if not elem.tail or not elem.tail.strip():
                        elem.tail = i
                else:
                    if level and (not elem.tail or not elem.tail.strip()):
                        elem.tail = i

            indent(root)
            tree.write(xml_path, encoding='UTF-8', xml_declaration=True)

            # 5. Compile XML back to ICC Binary
            subprocess.run([xml_to_icc, xml_path, icc_path], check=True)

            # 6. Apply profile via kscreen-doctor output pipeline
            cmd = ['kscreen-doctor', f'output.{display}.iccprofile.{icc_path}']
            subprocess.run(cmd, check=True)
            
            # 7. Alternating profile scheme automatically overrides old cache files.
            pass

            return True, "Success"

        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, str(e)

class MainWindow(QMainWindow):
    """
    Main GUI Window representing parameters and sliders for Display Saturation Control.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Maple Saturation Control")
        self.resize(520, 480)
        self.setStyleSheet(DesignSystem.STYLESHEET)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setSpacing(16)
        self.layout.setContentsMargins(32, 32, 32, 32)

        # Header Title
        header_layout = QHBoxLayout()
        title_label = QLabel("MAPLE SATURATION CONTROL")
        title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {DesignSystem.COLOR_TEXT}; letter-spacing: 2px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        self.layout.addLayout(header_layout)

        # Environment Verification Status
        warn_msg = QLabel("Active Compositor: KDE Plasma KWin Wayland color engine.")
        warn_msg.setStyleSheet(f"color: {DesignSystem.COLOR_BACKGROUND}; background-color: {DesignSystem.COLOR_SUCCESS}; padding: 12px; border-radius: 6px; font-weight: bold;")
        warn_msg.setWordWrap(True)
        self.layout.addWidget(warn_msg)
            
        btn_kcm = QPushButton("OPEN SYSTEM DISPLAY SETTINGS")
        btn_kcm.setStyleSheet(f"background-color: {DesignSystem.COLOR_ACCENT}; color: {DesignSystem.COLOR_BACKGROUND};")
        def open_kcm():
            cmds = [
                ["kcmshell6", "kcm_kscreen"],
                ["systemsettings", "kcm_kscreen"],
                ["systemsettings5", "kcm_kscreen"]
            ]
            success = False
            for cmd in cmds:
                try:
                    subprocess.Popen(cmd)
                    success = True
                    break
                except FileNotFoundError:
                    continue
            if not success:
                QMessageBox.warning(self, "Error", "Could not execute system settings dashboard.")
        btn_kcm.clicked.connect(open_kcm)
        self.layout.addWidget(btn_kcm)

        # Display Selection List
        self.display_combo = QComboBox()
        self.refresh_displays()
        self.layout.addWidget(QLabel("Target Display output:"))
        self.layout.addWidget(self.display_combo)

        # Saturation parameter box
        self.sat_group = QGroupBox("DIGITAL VIBRANCE (Color Saturation)")
        sat_layout = QVBoxLayout()
        
        self.sat_slider = QSlider(Qt.Orientation.Horizontal)
        self.sat_slider.setRange(0, 400)
        self.sat_slider.setValue(100)
        self.sat_slider.setSingleStep(5)
        self.sat_slider.setPageStep(5)
        self.sat_slider.valueChanged.connect(self.sync_sat_spin)
        
        # Saturation Numeric Input Box with custom buttons below
        sat_num_container = QWidget()
        sat_num_layout = QVBoxLayout(sat_num_container)
        sat_num_layout.setContentsMargins(0, 0, 0, 0)
        sat_num_layout.setSpacing(4)
        
        self.sat_spin = QDoubleSpinBox()
        self.sat_spin.setRange(0.0, 4.0)
        self.sat_spin.setSingleStep(0.05)
        self.sat_spin.setValue(1.0)
        self.sat_spin.setFixedWidth(80)
        self.sat_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.sat_spin.valueChanged.connect(self.sync_sat_slider)
        self.sat_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        sat_buttons_layout = QHBoxLayout()
        sat_buttons_layout.setSpacing(4)
        
        self.btn_sat_down = QPushButton("-")
        self.btn_sat_down.setFixedWidth(38)
        self.btn_sat_down.setFixedHeight(24)
        self.btn_sat_down.setStyleSheet(f"background-color: #23233B; color: {DesignSystem.COLOR_TEXT}; font-weight: bold; border-radius: 4px; padding: 2px;")
        self.btn_sat_down.clicked.connect(lambda: self.sat_spin.setValue(self.sat_spin.value() - 0.05))
        
        self.btn_sat_up = QPushButton("+")
        self.btn_sat_up.setFixedWidth(38)
        self.btn_sat_up.setFixedHeight(24)
        self.btn_sat_up.setStyleSheet(f"background-color: #23233B; color: {DesignSystem.COLOR_TEXT}; font-weight: bold; border-radius: 4px; padding: 2px;")
        self.btn_sat_up.clicked.connect(lambda: self.sat_spin.setValue(self.sat_spin.value() + 0.05))
        
        sat_buttons_layout.addWidget(self.btn_sat_down)
        sat_buttons_layout.addWidget(self.btn_sat_up)
        
        sat_num_layout.addWidget(self.sat_spin)
        sat_num_layout.addLayout(sat_buttons_layout)
        
        h_sat = QHBoxLayout()
        h_sat.addWidget(self.sat_slider)
        h_sat.addWidget(sat_num_container)
        sat_layout.addLayout(h_sat)
        self.sat_group.setLayout(sat_layout)
        self.layout.addWidget(self.sat_group)

        # Gamma contrast parameter box
        self.gamma_group = QGroupBox("CONTRAST VIBRANCE (Gamma Curve)")
        gamma_layout = QVBoxLayout()
        
        self.gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self.gamma_slider.setRange(10, 300)
        self.gamma_slider.setValue(100)
        self.gamma_slider.setSingleStep(5)
        self.gamma_slider.setPageStep(5)
        self.gamma_slider.valueChanged.connect(self.sync_gamma_spin)
        
        # Gamma Numeric Input Box with custom buttons below
        gamma_num_container = QWidget()
        gamma_num_layout = QVBoxLayout(gamma_num_container)
        gamma_num_layout.setContentsMargins(0, 0, 0, 0)
        gamma_num_layout.setSpacing(4)
        
        self.gamma_spin = QDoubleSpinBox()
        self.gamma_spin.setRange(0.1, 3.0)
        self.gamma_spin.setSingleStep(0.05)
        self.gamma_spin.setValue(1.0)
        self.gamma_spin.setFixedWidth(80)
        self.gamma_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.gamma_spin.valueChanged.connect(self.sync_gamma_slider)
        self.gamma_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        gamma_buttons_layout = QHBoxLayout()
        gamma_buttons_layout.setSpacing(4)
        
        self.btn_gamma_down = QPushButton("-")
        self.btn_gamma_down.setFixedWidth(38)
        self.btn_gamma_down.setFixedHeight(24)
        self.btn_gamma_down.setStyleSheet(f"background-color: #23233B; color: {DesignSystem.COLOR_TEXT}; font-weight: bold; border-radius: 4px; padding: 2px;")
        self.btn_gamma_down.clicked.connect(lambda: self.gamma_spin.setValue(self.gamma_spin.value() - 0.05))
        
        self.btn_gamma_up = QPushButton("+")
        self.btn_gamma_up.setFixedWidth(38)
        self.btn_gamma_up.setFixedHeight(24)
        self.btn_gamma_up.setStyleSheet(f"background-color: #23233B; color: {DesignSystem.COLOR_TEXT}; font-weight: bold; border-radius: 4px; padding: 2px;")
        self.btn_gamma_up.clicked.connect(lambda: self.gamma_spin.setValue(self.gamma_spin.value() + 0.05))
        
        gamma_buttons_layout.addWidget(self.btn_gamma_down)
        gamma_buttons_layout.addWidget(self.btn_gamma_up)
        
        gamma_num_layout.addWidget(self.gamma_spin)
        gamma_num_layout.addLayout(gamma_buttons_layout)
        
        h_gamma = QHBoxLayout()
        h_gamma.addWidget(self.gamma_slider)
        h_gamma.addWidget(gamma_num_container)
        gamma_layout.addLayout(h_gamma)
        self.gamma_group.setLayout(gamma_layout)
        self.layout.addWidget(self.gamma_group)

        # Operational Action Layout
        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("RESET DEFAULTS")
        self.btn_reset.setStyleSheet(f"background-color: #23233B; color: {DesignSystem.COLOR_TEXT};")
        self.btn_reset.clicked.connect(self.reset_defaults)
        
        self.btn_apply = QPushButton("APPLY SETTINGS")
        self.btn_apply.setStyleSheet(f"background-color: {DesignSystem.COLOR_PRIMARY}; color: {DesignSystem.COLOR_BACKGROUND};")
        self.btn_apply.clicked.connect(self.apply_settings)
        
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_apply)
        self.layout.addLayout(btn_layout)

        # System Bar Status message logger
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Restore saved config settings
        saved_settings = SettingsManager.load_settings()
        if saved_settings:
            saved_sat = saved_settings.get('saturation', 1.0)
            saved_gamma = saved_settings.get('gamma', 1.0)
            self.sat_spin.setValue(float(saved_sat))
            self.gamma_spin.setValue(float(saved_gamma))
            
            # Automatically apply the restored configuration to the active monitor on startup
            self.apply_settings()

    def refresh_displays(self):
        self.display_combo.clear()
        displays = DisplayController.get_connected_displays()
        if displays:
            self.display_combo.addItems(displays)
            index = self.display_combo.findText("eDP-1", Qt.MatchFlag.MatchContains)
            if index >= 0:
                self.display_combo.setCurrentIndex(index)
        else:
            self.display_combo.addItem("No connected displays detected")

    def sync_sat_spin(self, value):
        snapped_value = round(value / 5.0) * 5
        if snapped_value != value:
            self.sat_slider.setValue(snapped_value)
            return
        self.sat_spin.setValue(snapped_value / 100.0)

    def sync_sat_slider(self, value):
        snapped_val = round(value * 100.0 / 5.0) * 5
        self.sat_slider.setValue(snapped_val)

    def sync_gamma_spin(self, value):
        snapped_value = round(value / 5.0) * 5
        if snapped_value != value:
            self.gamma_slider.setValue(snapped_value)
            return
        self.gamma_spin.setValue(snapped_value / 100.0)

    def sync_gamma_slider(self, value):
        snapped_val = round(value * 100.0 / 5.0) * 5
        self.gamma_slider.setValue(snapped_val)

    def apply_settings(self):
        display = self.display_combo.currentText()
        if not display or "No connected" in display:
            self.status_bar.showMessage("Error: display target selection invalid.")
            return

        sat_val = self.sat_spin.value()
        gamma_val = self.gamma_spin.value()
        
        success, msg = DisplayController.apply_profile_wayland(display, sat_val, gamma_val)
        if not success:
            self.status_bar.showMessage(f"Error: {msg}", 5000)
            QMessageBox.critical(self, "Application Error", f"Failed applying profile changes: {msg}")
        else:
            self.status_bar.showMessage("Settings applied successfully to monitor target.", 5000)
            SettingsManager.save_settings(sat_val, gamma_val)

    def reset_defaults(self):
        self.sat_spin.setValue(1.0)
        self.gamma_spin.setValue(1.0)
        self.apply_settings()

if __name__ == "__main__":
    import argparse
    
    # Configure argument parsing for silent startup options
    parser = argparse.ArgumentParser(description="Maple Saturation Control")
    parser.add_argument('--apply', action='store_true', help="Apply saved configuration silently and exit")
    args = parser.parse_known_args()[0]
    
    if args.apply:
        # Initialize minimal application context for system calls
        app = QApplication(sys.argv)
        
        saved_settings = SettingsManager.load_settings()
        sat_val = float(saved_settings.get('saturation', 1.0))
        gamma_val = float(saved_settings.get('gamma', 1.0))
        
        displays = DisplayController.get_connected_displays()
        if displays:
            display = displays[0]
            success, msg = DisplayController.apply_profile_wayland(display, sat_val, gamma_val)
            if success:
                print(f"Successfully applied saved color configuration (Sat: {sat_val}, Gamma: {gamma_val}) to {display}.")
                sys.exit(0)
            else:
                print(f"Error applying configuration: {msg}")
                sys.exit(1)
        else:
            print("Error: No active displays detected.")
            sys.exit(1)
            
    else:
        # Default graphical user interface mode
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

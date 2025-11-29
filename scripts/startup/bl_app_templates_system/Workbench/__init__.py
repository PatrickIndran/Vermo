# ------------------------------------------------------------------------
#    Workbench Application Template
# ------------------------------------------------------------------------

bl_info = {
    "name": "Workbench",
    "author": "Studio Pipeline",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > New > Workbench",
    "description": "Asset Management Workspace: Automated folder structures for Characters, Props, and Resources.",
    "category": "Application Template",
}

import bpy
import os
import shutil
from bpy.app.handlers import persistent

# ------------------------------------------------------------------------
#    CONSTANTS & CONFIG
# ------------------------------------------------------------------------

TYPE_ITEMS = [
    ('prp', "Prop (prp)", "Standard Prop Asset", 'OBJECT_DATAMODE', 0),
    ('chr', "Character (chr)", "Character/Rig Asset", 'OUTLINER_OB_ARMATURE', 1),
    ('res', "Resource (res)", "General Resource or Environment", 'WORLD', 2),
]

# ------------------------------------------------------------------------
#    DATA PROPERTIES
# ------------------------------------------------------------------------

class StudioProjectProps(bpy.types.PropertyGroup):
    base_path: bpy.props.StringProperty(
        name="Root Path",
        default="//",
        subtype='DIR_PATH',
        description="The root directory where the project folder will be created"
    )
    
    asset_type: bpy.props.EnumProperty(
        name="Asset Type", 
        items=TYPE_ITEMS, 
        default='prp'
    )
    
    asset_name: bpy.props.StringProperty(
        name="Asset Name", 
        default="New_Asset",
        description="The unique name of the asset (no spaces recommended)"
    )
    
    version: bpy.props.IntProperty(
        name="Version", 
        default=1, 
        min=1,
        description="Current working version"
    )
    
    # Internal flag to track if the project has been initialized
    is_generated: bpy.props.BoolProperty(default=False)

# ------------------------------------------------------------------------
#    PATH UTILITIES
# ------------------------------------------------------------------------

def get_project_root(scene):
    """Returns: /Path/To/Root/prp_Asset"""
    props = scene.studio_props
    # Clean up name to be safe for folders
    safe_name = props.asset_name.replace(" ", "_")
    folder_name = f"{props.asset_type}_{safe_name}"
    return os.path.join(bpy.path.abspath(props.base_path), folder_name)

def get_version_folder(scene, version_int):
    """Returns: .../prp_Asset/v01"""
    root = get_project_root(scene)
    return os.path.join(root, f"v{version_int:02d}")

def get_arch_folder(scene):
    """Returns: .../prp_Asset/arch"""
    root = get_project_root(scene)
    return os.path.join(root, "arch")

def get_blend_filename(scene, version_int, state='wip'):
    """Returns: prp_Asset_v01_wip.blend"""
    props = scene.studio_props
    safe_name = props.asset_name.replace(" ", "_")
    return f"{props.asset_type}_{safe_name}_v{version_int:02d}_{state}.blend"

# ------------------------------------------------------------------------
#    OPERATORS
# ------------------------------------------------------------------------

class STUDIO_OT_create_structure(bpy.types.Operator):
    """Initialize the project folders and save the first file"""
    bl_idname = "studio.create_structure"
    bl_label = "Initialize Workbench"
    bl_icon = "FILE_NEW"

    def execute(self, context):
        props = context.scene.studio_props
        
        # 1. Define paths for v01
        ver_folder = get_version_folder(context.scene, props.version)
        wip_dir = os.path.join(ver_folder, "wip", "projects")
        fin_dir = os.path.join(ver_folder, "fin", "projects")
        arch_dir = get_arch_folder(context.scene)
        
        # 2. Create physical folders
        try:
            os.makedirs(wip_dir, exist_ok=True)
            os.makedirs(fin_dir, exist_ok=True)
            os.makedirs(arch_dir, exist_ok=True)
        except OSError as e:
            self.report({'ERROR'}, f"Could not create folders: {e}")
            return {'CANCELLED'}

        # 3. Save the initial .blend file
        fname = get_blend_filename(context.scene, props.version, state='wip')
        full_path = os.path.join(wip_dir, fname)

        try:
            bpy.ops.wm.save_as_mainfile(filepath=full_path)
            props.is_generated = True
            self.report({'INFO'}, f"Workbench Initialized: {fname}")
        except Exception as e:
            self.report({'ERROR'}, f"Could not save file: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


class STUDIO_OT_archive_and_iterate(bpy.types.Operator):
    """Archive current version and start the next"""
    bl_idname = "studio.archive_iterate"
    bl_label = "Version Up"
    bl_description = "Moves current version to Archive and starts a fresh file"
    bl_icon = "PACKAGE"

    wipe_scene: bpy.props.BoolProperty(
        name="Clear Scene", 
        description="Delete all objects for the new version?", 
        default=True
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        props = context.scene.studio_props
        current = props.version
        
        box = layout.box()
        box.label(text=f"Archive: v{current:02d}", icon='FILE_FOLDER')
        box.label(text=f"Create:  v{current+1:02d}", icon='FILE_NEW')
        
        layout.separator()
        layout.prop(self, "wipe_scene")

    def execute(self, context):
        props = context.scene.studio_props
        
        cur_ver = props.version
        next_ver = cur_ver + 1
        
        old_ver_folder = get_version_folder(context.scene, cur_ver)
        arch_root = get_arch_folder(context.scene)
        
        # 1. Setup Next Version Folders
        new_ver_folder = get_version_folder(context.scene, next_ver)
        new_wip_dir = os.path.join(new_ver_folder, "wip", "projects")
        new_fin_dir = os.path.join(new_ver_folder, "fin", "projects")
        
        os.makedirs(new_wip_dir, exist_ok=True)
        os.makedirs(new_fin_dir, exist_ok=True)
        
        # 2. Wipe Scene (Optional)
        if self.wipe_scene:
            # Select all and delete
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()
            # Clean unused meshes/materials
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        # 3. Save New Version File
        new_fname = get_blend_filename(context.scene, next_ver, state='wip')
        new_filepath = os.path.join(new_wip_dir, new_fname)
        
        bpy.ops.wm.save_as_mainfile(filepath=new_filepath)
        
        # 4. Move Old Version to Archive
        # We check if folder exists to avoid errors
        if os.path.exists(old_ver_folder):
            dest_in_arch = os.path.join(arch_root, f"v{cur_ver:02d}")
            if not os.path.exists(dest_in_arch):
                try:
                    shutil.move(old_ver_folder, dest_in_arch)
                    self.report({'INFO'}, f"v{cur_ver:02d} Archived.")
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to move to archive: {e}")
            else:
                self.report({'WARNING'}, f"Archive for v{cur_ver:02d} already exists.")

        # 5. Update Version Property
        props.version = next_ver

        return {'FINISHED'}


class STUDIO_OT_finalize(bpy.types.Operator):
    """Save a copy to the FIN folder"""
    bl_idname = "studio.finalize"
    bl_label = "Publish Final"
    bl_description = "Saves a copy to the 'fin' folder"
    bl_icon = "CHECKBOX_HLT"

    def execute(self, context):
        props = context.scene.studio_props
        
        ver_folder = get_version_folder(context.scene, props.version)
        fin_dir = os.path.join(ver_folder, "fin", "projects")
        
        if not os.path.exists(fin_dir):
            os.makedirs(fin_dir, exist_ok=True)
            
        fname = get_blend_filename(context.scene, props.version, state='fin')
        path = os.path.join(fin_dir, fname)
        
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
        self.report({'INFO'}, f"Published Final: {fname}")
        
        return {'FINISHED'}

class STUDIO_OT_startup_dialog(bpy.types.Operator):
    bl_idname = "studio.startup_dialog"
    bl_label = "Workbench Setup"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        props = context.scene.studio_props
        
        layout.label(text="Project Settings", icon='PREFERENCES')
        
        box = layout.box()
        box.prop(props, "base_path")
        
        box = layout.box()
        row = box.row()
        row.prop(props, "asset_type", text="")
        row.prop(props, "asset_name", text="")
        
        layout.separator()
        layout.label(text="Initial Version: v01")

    def execute(self, context):
        return bpy.ops.studio.create_structure()

# ------------------------------------------------------------------------
#    UI PANEL
# ------------------------------------------------------------------------

class STUDIO_PT_asset_management(bpy.types.Panel):
    bl_label = "Workbench"
    bl_idname = "STUDIO_PT_asset_management"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Workbench'

    def draw(self, context):
        layout = self.layout
        props = context.scene.studio_props

        # If project isn't set up, show the setup button
        if not props.is_generated:
            col = layout.column(align=True)
            col.scale_y = 1.5
            col.operator("studio.startup_dialog", text="Setup Project", icon='FILE_NEW')
            return

        # Main Interface
        box = layout.box()
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text=f"{props.asset_name}", icon='OUTLINER_OB_GROUP_INSTANCE')
        row.label(text=f"v{props.version:02d}")

        layout.separator()
        
        # Operations
        col = layout.column(align=True)
        col.scale_y = 1.2
        col.operator("studio.finalize", text="Publish Final")
        col.operator("studio.archive_iterate", text="Version Up")
        
        layout.separator()
        
        # Footer info
        sub = layout.column(align=True)
        sub.active = False
        sub.label(text="Current State: WIP", icon='TIME')
        
        # Show truncated path for sanity check
        path = os.path.dirname(bpy.data.filepath)
        folder_name = os.path.basename(path) if path else "Unsaved"
        sub.label(text=f"Folder: .../{folder_name}/")

# ------------------------------------------------------------------------
#    REGISTRATION
# ------------------------------------------------------------------------

classes = (
    StudioProjectProps,
    STUDIO_OT_create_structure,
    STUDIO_OT_startup_dialog,
    STUDIO_OT_archive_and_iterate,
    STUDIO_OT_finalize,
    STUDIO_PT_asset_management,
)

@persistent
def workbench_load_handler(dummy):
    """
    Checks on startup if this file was created by the template.
    If not, it prompts the user to set up the project.
    """
    try:
        if not bpy.context.scene.studio_props.is_generated:
            # Use a timer to ensure the UI is ready before showing the dialog
            bpy.app.timers.register(lambda: bpy.ops.studio.startup_dialog('INVOKE_DEFAULT'), first_interval=0.1)
    except AttributeError:
        pass

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.studio_props = bpy.props.PointerProperty(type=StudioProjectProps)
    
    # Register the handler that makes this behave like an App Template
    if workbench_load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(workbench_load_handler)

def unregister():
    if workbench_load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(workbench_load_handler)
        
    del bpy.types.Scene.studio_props
    
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
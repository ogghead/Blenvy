import bpy
import json
from mathutils import Vector

from ..helpers_collections import set_active_collection
from ..blenvy_manager import BlenvyManager

""" This file contains quality of life operators/menus/shortcuts to make working with blueprints more pleasant
* based on the excellent work by slyedoc: https://github.com/slyedoc/bevy_sly_blender/tree/4223cc0ff86255f82bb555ffc8eddf65e91aa636

- [x] detect editing in progress
- [x] select collection instead of objects 
- [x] if current scene (before edit) 
    - is library: do not create instance
    - is main scene: create instance
    - or alternative: sub menu to choose instance creation or not
- [x] save & restore blenvy mode
- [x] add a contextual shortcut to easilly jump in/out of editing mode
- [ ] if editing is already in progress close it first
    - [ ] do this for the wrapper
    - [x] do this for the shortcut
    - [ ] move the "close first" logic to inside create & edit operators
- [ ] also allow triggering editing from library scene with collection selected
    => requires checking if collection is a blueprint's collection
- [x] do not go in create mode if there is an object (not a collection !) selected
- [ ] save & reset camera
"""

def edit_or_create_blueprint_menu(self, context):
    if bpy.context.active_object and bpy.context.active_object.instance_collection:
        self.layout.operator(BLENVY_OT_ui_blueprint_edit_start.bl_idname)
    else:
        blenvy = context.window_manager.blenvy # type: BlenvyManager                
        prev_scene = bpy.data.scenes.get(blenvy.edit_blueprint_previous_scene)
        if prev_scene is not None:
            self.layout.operator(BLENVY_OT_ui_blueprint_edit_end.bl_idname)
        else:
            self.layout.operator(BLENVY_OT_ui_blueprint_create.bl_idname)
        
def find_viewport_camera():
    def find_area():
        try:
            for a in bpy.data.window_managers[0].windows[0].screen.areas:
                if a.type == "VIEW_3D":
                    return a
            return None
        except:
            return None

    area = find_area()

    if area is None:
        print("area not find")
    else:
        # print(dir(area))
        r3d = area.spaces[0].region_3d
        view_mat = r3d.view_matrix
        print("view matrix: ", view_mat)

        loc, rot, sca = view_mat.decompose()
        print("location xyz: ", loc)
        print("rotation wxyz: ", rot)
        print("scale xyz: ", sca)
        print("")
        print("view_distance: ", r3d.view_distance)
        print("view_location: ", r3d.view_location)
        print("view_rotation: ", r3d.view_rotation)
        print("view_camera_zoom: ", r3d.view_camera_zoom)
        print("view_distance: ", r3d.view_distance)
        print("view_camera_offset: ", r3d.view_camera_offset)


class BLENVY_OT_ui_blueprint_create_or_edit(bpy.types.Operator):
    """Create Blueprint in a new Scene"""
    bl_idname = "window_manager.blenvy_blueprint_shortcut"
    bl_label = "Edit Blueprint"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):        
        blenvy = context.window_manager.blenvy # type: BlenvyManager    
        if bpy.context.active_object and bpy.context.active_object.instance_collection:
            if blenvy.edit_blueprint_current_scene != "": # if there is already editing in progress, close it first
                bpy.ops.window_manager.blenvy_exit_edit_blueprint()
            bpy.ops.window_manager.blenvy_blueprint_edit_start()
        else:
            blenvy = context.window_manager.blenvy # type: BlenvyManager                
            prev_scene = bpy.data.scenes.get(blenvy.edit_blueprint_previous_scene)
            if prev_scene is not None:
                bpy.ops.window_manager.blenvy_exit_edit_blueprint()
            else:
                if len(context.selected_objects) == 0: # do not go into creation mode if any object was selected
                    if blenvy.edit_blueprint_current_scene != "": # if there is already editing in progress, close it first
                        bpy.ops.window_manager.blenvy_exit_edit_blueprint()
                    bpy.ops.window_manager.blenvy_create_blueprint()
        
        return {"FINISHED"}

class BLENVY_OT_ui_blueprint_create(bpy.types.Operator):
    """Create Blueprint in a new Scene"""
    bl_idname = "window_manager.blenvy_create_blueprint"
    bl_label = "Create Blueprint"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):        
        blenvy = context.window_manager.blenvy # type: BlenvyManager        

        # Store original Blenvy setting
        blenvy.edit_blueprint_previous_scene = bpy.context.scene.name
        blenvy.edit_blueprint_previous_mode = blenvy.mode

        # set mode to components for easier editing
        blenvy.mode = "COMPONENTS"

        blueprint_name = "new_blueprint"
        collection = bpy.data.collections.new(blueprint_name)
        
        library_scene_name = "Library"
        if len(blenvy.library_scenes_names) > 0:
            library_scene_name = blenvy.library_scenes_names[0]
        else:
            bpy.data.scenes.new(library_scene_name)
        # automatically add it to the library : find library scene, if any, if not, create it 
        bpy.data.scenes[library_scene_name].collection.children.link(collection)
        
        


        # create an instance of the blueprint ONLY the current scene we are in is a level scene
        if context.scene.blenvy_scene_type == 'Level':
            source_collection = collection
            instance_obj = bpy.data.objects.new(
                name=collection.name, 
                object_data=None
            )
            instance_obj.instance_collection = source_collection
            instance_obj.instance_type = 'COLLECTION'
            parent_collection = bpy.context.view_layer.active_layer_collection
            parent_collection.collection.objects.link(instance_obj)

        # now open the temporary scene
        scene_name = f"EDITING:{blueprint_name}"
        bpy.ops.scene.new(type="EMPTY")
        new_scene = bpy.context.scene
        new_scene.name = scene_name
        bpy.context.window.scene = new_scene

        new_scene.collection.children.link(collection)

        # flag the current temporary scene as an active edit
        blenvy.edit_blueprint_current_scene = scene_name

        # deselect all objects then select the first object in new scene
        bpy.ops.object.select_all(action='DESELECT')        

        # zoom to selected
        bpy.ops.view3d.view_selected()
        # now that the 3d view has been adapted, we select what we actually need: the collection/blueprint
        bpy.ops.blenvy.select_item(target_name=collection.name, item_type="COLLECTION", override_scene_name=scene_name)

        return {"FINISHED"}

class BLENVY_OT_ui_blueprint_edit_start(bpy.types.Operator):
    """Edit the Blueprint referenced by this Blueprint Instance in a new Scene"""
    bl_idname = "window_manager.blenvy_blueprint_edit_start"
    bl_label = "Start Editing Blueprint"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):        
        blenvy = context.window_manager.blenvy # type: BlenvyManager        
        collection = bpy.context.active_object.instance_collection

        # Store original Blenvy setting
        blenvy.edit_blueprint_previous_scene = bpy.context.scene.name
        blenvy.edit_blueprint_previous_mode = blenvy.mode

        # set mode to components
        blenvy.mode = "COMPONENTS"

        if not collection:
            print("Active item is not a Blueprint/Collection instance")
            self.report({"WARNING"}, "Active item is not a Blueprint/Collection instance")
            return {"CANCELLED"}

        scene_name = f"EDITING:{collection.name}"
        bpy.ops.scene.new(type="EMPTY")
        new_scene = bpy.context.scene
        new_scene.name = scene_name
        bpy.context.window.scene = new_scene
        new_scene.collection.children.link(collection)

        # flag the current temporary scene as an active edit
        blenvy.edit_blueprint_current_scene = scene_name


        # Assuming you want to focus on the objects from the linked collection
        # Switch to the new scene context        
        
        """blenvy.edit_collection_world_texture = "checker"
        if blenvy.edit_collection_world_texture != "none":
            world = bpy.data.worlds.new(bpy.context.scene.name)
            new_scene.world = world
            world.use_nodes = True
            tree = world.node_tree

            if blenvy.edit_collection_world_texture in ["checker", "checker_view"]:
                checker_texture = tree.nodes.new("ShaderNodeTexChecker")
                checker_texture.inputs["Scale"].default_value = 20
                checker_texture.location = Vector((-250, 0))
                if blenvy.edit_collection_world_texture == "checker_view":
                    coord = tree.nodes.new("ShaderNodeTexCoord")
                    coord.location = Vector((-500, 0))
                    for op in coord.outputs:
                        op.hide = True
                    tree.links.new(coord.outputs["Window"], checker_texture.inputs["Vector"])
                tree.links.new(checker_texture.outputs["Color"], tree.nodes["Background"].inputs["Color"])
            elif blenvy.edit_collection_world_texture == "gray":
                tree.nodes["Background"].inputs["Color"].default_value = (.3, .3, .3, 1)"""

        # deselect all objects then select the first object in new scene
        bpy.ops.object.select_all(action='DESELECT')        

        # find the root object
        if len(collection.objects) > 0 :
            root_obj = collection.objects[0]
            while root_obj.parent:
                root_obj = root_obj.parent            
            
            # select object and children
            new_scene.objects[root_obj.name].select_set(True)        
            # def select_children(parent):
            #     for child in parent.children:
            #         child.select_set(True)
            #         select_children(child)  # Recursively select further descendants
            # select_children(root_obj);

            # Select the view layer and view the selected objects
            bpy.context.view_layer.objects.active = new_scene.objects[root_obj.name]
            bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[collection.name]

            # zoom to selected
            bpy.ops.view3d.view_selected()
        
        # now that the 3d view has been adapted, we select what we actually need: the collection/blueprint        
        bpy.ops.blenvy.select_item(target_name=collection.name, item_type="COLLECTION", override_scene_name=scene_name)

        return {"FINISHED"}
    
class BLENVY_OT_ui_blueprint_edit_end(bpy.types.Operator):    
    bl_idname = "window_manager.blenvy_exit_edit_blueprint"
    bl_label = "Done editing blueprint"
    bl_options = {"UNDO"}
    
    def execute(self, context):
        blenvy = context.window_manager.blenvy # type: BlenvyManager        
        # = context.window_manager.bevy # type: BlenvyManager
        
        current_scene = bpy.context.scene      
        prev_scene = bpy.data.scenes.get(blenvy.edit_blueprint_previous_scene)

        # we are done editing the blueprint, reset settings to the way they were before
        blenvy.edit_blueprint_previous_scene = ""
        blenvy.mode = blenvy.edit_blueprint_previous_mode


        if prev_scene is None:
            print("No scene to return to")
            return {'CANCELLED'}
        if blenvy.edit_blueprint_current_scene != "":
            active_edit_scene = bpy.data.scenes.get(blenvy.edit_blueprint_current_scene, None)
            if active_edit_scene is not None:
                bpy.data.scenes.remove(active_edit_scene)

                # if we are not in the active edit scene
                try:
                    if blenvy.edit_blueprint_current_scene != current_scene.name:
                        bpy.context.window.scene = current_scene
                    else:
                        bpy.context.window.scene = prev_scene
                except: 
                    bpy.context.window.scene = prev_scene
            """if current_scene.name.startswith("EDITING:"):
                bpy.data.scenes.remove(bpy.context.scene)
                bpy.context.window.scene = prev_scene"""
            blenvy.edit_blueprint_current_scene = ""

        else:
            blenvy.edit_blueprint_current_scene = ""
            print("Not in temp scene")
            return {'CANCELLED'}
        
        

        return {'FINISHED'}


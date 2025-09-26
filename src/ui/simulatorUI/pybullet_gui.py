import json
import time
import math
import traceback
import threading
import queue
import numpy as np
import pybullet as p


def safe_get_from_queue(q, timeout=0.001):
    """Safely get item from queue with timeout"""
    try:
        return q.get_nowait()
    except queue.Empty:
        return None

def load_shapes(shapes, robot_id):
    """Load all shapes into PyBullet environment"""
    loaded_shapes = []
    print(f"Loading shapes. Total shapes to load: {len(shapes)}")

    for shape in shapes:
        # Skip robot model (avoid duplicate loading)
        if robot_id is not None and shape.get('id') == robot_id:
            continue

        try:
            shape_type = shape.get('type')
            category = shape.get('category')

            if category == 'collision':
                # Handle collision shapes
                params = shape.get('parameters', {})
                position = params.get('position', [0, 0, 0])
                orientation = params.get('orientation', [0, 0, 0, 1])

                collision_id = -1
                if shape_type == 'sphere':
                    radius = params.get('radius', 1.0)
                    collision_id = p.createCollisionShape(p.GEOM_SPHERE, radius=radius)
                elif shape_type == 'box':
                    half_extents = [
                        params.get('length', 1.0) / 2,
                        params.get('width', 1.0) / 2,
                        params.get('height', 1.0) / 2
                    ]
                    collision_id = p.createCollisionShape(p.GEOM_BOX, halfExtents=half_extents)
                elif shape_type == 'cylinder':
                    radius = params.get('radius', 1.0)
                    height = params.get('height', 1.0)
                    collision_id = p.createCollisionShape(p.GEOM_CYLINDER, radius=radius, height=height)
                elif shape_type == 'capsule':
                    radius = params.get('radius', 1.0)
                    height = params.get('height', 1.0)
                    collision_id = p.createCollisionShape(p.GEOM_CAPSULE, radius=radius, height=height)

                if collision_id != -1:
                    body_id = p.createMultiBody(
                        baseMass=params.get('mass', 0),
                        baseCollisionShapeIndex=collision_id,
                        basePosition=position,
                        baseOrientation=orientation
                    )
                    loaded_shapes.append(body_id)
                    print(f"Loaded collision shape: {shape_type}, ID: {body_id}")

            elif category == 'visual':
                # Handle visual shapes
                params = shape.get('parameters', {})
                position = params.get('position', [0, 0, 0])
                orientation = params.get('orientation', [0, 0, 0, 1])
                rgba_color = params.get('rgba_color', [1, 1, 1, 1])

                visual_id = -1
                collision_id = -1

                if shape_type == 'sphere':
                    radius = params.get('radius', 1.0)
                    visual_id = p.createVisualShape(p.GEOM_SPHERE, radius=radius, rgbaColor=rgba_color)
                    collision_id = p.createCollisionShape(p.GEOM_SPHERE, radius=radius)
                elif shape_type == 'box':
                    half_extents = [
                        params.get('length', 1.0) / 2,
                        params.get('width', 1.0) / 2,
                        params.get('height', 1.0) / 2
                    ]
                    visual_id = p.createVisualShape(p.GEOM_BOX, halfExtents=half_extents, rgbaColor=rgba_color)
                    collision_id = p.createCollisionShape(p.GEOM_BOX, halfExtents=half_extents)
                elif shape_type == 'cylinder':
                    radius = params.get('radius', 1.0)
                    height = params.get('height', 1.0)
                    visual_id = p.createVisualShape(p.GEOM_CYLINDER, radius=radius, length=height, rgbaColor=rgba_color)
                    collision_id = p.createCollisionShape(p.GEOM_CYLINDER, radius=radius, height=height)
                elif shape_type == 'capsule':
                    radius = params.get('radius', 1.0)
                    height = params.get('height', 1.0)
                    visual_id = p.createVisualShape(p.GEOM_CAPSULE, radius=radius, length=height, rgbaColor=rgba_color)
                    collision_id = p.createCollisionShape(p.GEOM_CAPSULE, radius=radius, height=height)

                if visual_id != -1 and collision_id != -1:
                    body_id = p.createMultiBody(
                        baseMass=params.get('mass', 0),
                        baseCollisionShapeIndex=collision_id,
                        baseVisualShapeIndex=visual_id,
                        basePosition=position,
                        baseOrientation=orientation
                    )
                    loaded_shapes.append(body_id)
                    print(f"Loaded visual shape: {shape_type}, ID: {body_id}")

            elif category == 'model':
                # Handle imported models
                file_path = shape.get('file_path')
                position = shape.get('position', [0, 0, 0])
                orientation = shape.get('orientation', [0, 0, 0, 1])

                if shape_type == '导入URDF' and file_path:
                    try:
                        body_id = p.loadURDF(
                            file_path,
                            basePosition=position,
                            baseOrientation=orientation,
                            useFixedBase=True
                        )
                        if body_id >= 0:
                            loaded_shapes.append(body_id)
                            print(f"Loaded URDF model. ID: {body_id}")
                    except Exception as e:
                        print(f"Failed to load URDF: {str(e)}")

                elif shape_type in ['导入OBJ', '导入STL'] and file_path:
                    try:
                        params = shape.get('parameters', {})
                        scale = params.get('scale', 1.0)
                        mass = params.get('mass', 1.0)

                        visual_id = p.createVisualShape(
                            shapeType=p.GEOM_MESH,
                            fileName=file_path,
                            meshScale=[scale, scale, scale]
                        )

                        collision_id = p.createCollisionShape(
                            shapeType=p.GEOM_MESH,
                            fileName=file_path,
                            meshScale=[scale, scale, scale]
                        )

                        if visual_id != -1 and collision_id != -1:
                            body_id = p.createMultiBody(
                                baseMass=mass,
                                baseCollisionShapeIndex=collision_id,
                                baseVisualShapeIndex=visual_id,
                                basePosition=position,
                                baseOrientation=orientation
                            )
                            if body_id >= 0:
                                loaded_shapes.append(body_id)
                                print(f"Loaded mesh model ({shape_type}). ID: {body_id}")
                    except Exception as e:
                        print(f"Failed to load mesh: {str(e)}")

        except Exception as e:
            print(f"Error loading shape: {str(e)}")

    print(f"Loading complete. Total loaded shapes: {len(loaded_shapes)}")
    return loaded_shapes

def update_robot_state(robot_id, joint_angles, tool_state, joint_config):
    """Update robot joint angles"""
    if robot_id is not None and joint_angles and joint_config:
        # Get joint group configuration
        main_group_includes = joint_config.get('main_group_includes', [])
        tool_group_includes = joint_config.get('tool_group_includes', [])
        joint_types = joint_config.get('joint_types', {})

        # Update main joint group (arm joints)
        for idx in main_group_includes:
            if idx < len(joint_angles):
                try:
                    # Convert angles to radians
                    angle_rad = math.radians(joint_angles[idx])

                    # Use position controller to maintain joint position, resisting gravity
                    p.setJointMotorControl2(
                        robot_id,
                        idx,
                        p.POSITION_CONTROL,
                        targetPosition=angle_rad,
                        force=1000.0  # Sufficient force to resist gravity
                    )

                except Exception as e:
                    print(f"Error updating main joint {idx}: {str(e)}")

        # Update tool joint group
        if tool_state:
            for i in range(len(tool_state)):
                if i < len(tool_group_includes):
                    joint_index = tool_group_includes[i]
                    # Keys in JSON are strings, need to convert integer to string
                    joint_type = joint_types.get(str(joint_index), "unknown")

                    try:
                        value = -1
                        if joint_type == "revolute":
                            value = math.radians(tool_state[i])
                        elif joint_type == "prismatic":
                            value = tool_state[i]
                        elif joint_type == "fixed":
                            # Fixed joints don't need control, skip them
                            continue

                        if value != -1:
                            # Use position controller to maintain tool joint position
                            p.setJointMotorControl2(
                                robot_id,
                                joint_index,
                                p.POSITION_CONTROL,
                                targetPosition=value,
                                force=500.0  # Tool joints usually require smaller force
                            )
                        else:
                            print(f"Unknown joint type '{joint_type}' for joint {joint_index}")

                    except Exception as e:
                        print(f"Error updating tool joint {joint_index}: {str(e)}")

def update_tcp_markers(position, orientation, length=0.05):
    """Create or update TCP coordinate system markers"""
    if not position or not orientation:
        return

    # Calculate rotation matrix
    rot_matrix = p.getMatrixFromQuaternion(orientation)
    rot_matrix = np.array(rot_matrix).reshape(3, 3)

    # If first time creating markers or markers have been deleted
    if not hasattr(update_tcp_markers, 'marker_ids'):
        update_tcp_markers.marker_ids = []
        # Draw new coordinate axes
        colors = [[1,0,0], [0,1,0], [0,0,1]]

        for i in range(3):
            axis_vector = rot_matrix[:, i] * length
            end_point = [
                position[0] + axis_vector[0],
                position[1] + axis_vector[1],
                position[2] + axis_vector[2]
            ]

            marker_id = p.addUserDebugLine(
                position,
                end_point,
                colors[i],
                lineWidth=2.0
            )
            update_tcp_markers.marker_ids.append(marker_id)
    else:
        # Update existing marker positions
        colors = [[1,0,0], [0,1,0], [0,0,1]]

        for i in range(3):
            axis_vector = rot_matrix[:, i] * length
            end_point = [
                position[0] + axis_vector[0],
                position[1] + axis_vector[1],
                position[2] + axis_vector[2]
            ]

            p.addUserDebugLine(
                position,
                end_point,
                colors[i],
                lineWidth=2.0,
                replaceItemUniqueId=update_tcp_markers.marker_ids[i]
            )

def update_shape_pose(shape_id, position, orientation):
    """Update pose of existing shape in GUI"""
    try:
        p.resetBasePositionAndOrientation(shape_id, position, orientation)
        print(f"Updated pose for shape ID: {shape_id}")
        return True
    except Exception as e:
        print(f"Failed to update pose for shape {shape_id}: {str(e)}")
        return False

def remove_shape_from_gui(shape_id):
    """Remove shape from GUI"""
    try:
        p.removeBody(shape_id)
        print(f"Removed shape with ID: {shape_id}")
        return True
    except Exception as e:
        print(f"Failed to remove shape {shape_id}: {str(e)}")
        return False

def pybullet_gui_process(robot_state_queue, offline_params_queue, shutdown_event):
    """PyBullet GUI process function that runs in a separate process using queues for communication

    Args:
        robot_state_queue: Queue for receiving robot state updates
        offline_params_queue: Queue for receiving offline parameter updates
        shutdown_event: Event to signal when to shutdown the process
    """
    try:
        # Global variables for this process
        marker_ids = []
        loaded_shapes = []
        loaded_shape_ids = set()
        shape_poses = {}
        robot_id = None
        offline_data = None

        # Start PyBullet GUI mode
        client_id = p.connect(p.GUI)
        p.configureDebugVisualizer(p.COV_ENABLE_GUI, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_MOUSE_PICKING, 1)
        p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 0)
        p.configureDebugVisualizer(p.COV_ENABLE_DEPTH_BUFFER_PREVIEW, 0)
        p.configureDebugVisualizer(p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW, 0)

        # Set camera view
        p.resetDebugVisualizerCamera(
            cameraDistance=0.3,
            cameraYaw=50,
            cameraPitch=-35,
            cameraTargetPosition=[0, 0, 0]
        )

        # Set gravity and other physics properties
        p.setGravity(0, 0, -9.81)

        # Disable real-time simulation, manually control simulation stepping
        p.setRealTimeSimulation(0)

        # Set physics engine parameters for improved stability
        p.setPhysicsEngineParameter(enableConeFriction=0)
        p.setPhysicsEngineParameter(numSolverIterations=10)
        p.setPhysicsEngineParameter(numSubSteps=1)
        p.setPhysicsEngineParameter(contactBreakingThreshold=0.001)

        # Wait for initial offline parameters
        print("Waiting for initial offline parameters...")
        while offline_data is None:
            offline_data = safe_get_from_queue(offline_params_queue)
            if offline_data is None:
                time.sleep(0.01)

        # Load URDF model
        urdf_path = offline_data.get('urdf_path')
        current_urdf_path = urdf_path  # Track current URDF path for change detection
        if urdf_path:
            try:
                robot_id = p.loadURDF(urdf_path, useFixedBase=True)
                print(f"Successfully loaded robot model: ID = {robot_id}")
            except Exception as e:
                print(f"Failed to load robot model: {str(e)}")

        # Load all shapes
        shapes = offline_data.get('shapes', [])
        loaded_shapes = load_shapes(shapes, robot_id)

        # Save loaded shape IDs for tracking newly added shapes
        for shape in shapes:
            if shape.get('id') is not None:
                loaded_shape_ids.add(shape['id'])
                # Cache initial poses
                params = shape.get('parameters', {})
                shape_poses[shape['id']] = {
                    'position': params.get('position', [0, 0, 0]),
                    'orientation': params.get('orientation', [0, 0, 0, 1])
                }

        # Wait for initial robot state
        print("Waiting for initial robot state...")
        initial_state = None
        while initial_state is None:
            initial_state = safe_get_from_queue(robot_state_queue)
            if initial_state is None:
                time.sleep(0.01)

        # Initialize robot state
        joint_angles = initial_state.get('joint_angles')
        if joint_angles:
            update_robot_state(robot_id, joint_angles, initial_state.get('tool_state'), offline_data.get('joint_config'))

        # Initialize base pose
        base_position = initial_state.get('base_position')
        base_orientation = initial_state.get('base_orientation')
        if base_position is not None and base_orientation is not None:
            try:
                p.resetBasePositionAndOrientation(robot_id, base_position, base_orientation)
                print(f"Initialized base pose: position={base_position}, orientation={base_orientation}")
            except Exception as e:
                print(f"Failed to initialize base pose: {str(e)}")

        # Initialize TCP markers
        target_position = initial_state.get('target_position')
        target_orientation = initial_state.get('target_orientation')
        if target_position and target_orientation:
            update_tcp_markers(target_position, target_orientation)

        print("starting GUI loop...")

        # Cache base pose for change detection
        cached_base_position = offline_data.get('base_position')
        cached_base_orientation = offline_data.get('base_orientation')

        # Main loop
        try:
            while p.isConnected() and not shutdown_event.is_set():
                # Check for offline parameter updates
                new_offline_data = safe_get_from_queue(offline_params_queue)
                if new_offline_data is not None:
                    offline_data = new_offline_data

                    # Check if should shutdown
                    if not offline_data.get('is_simulating', True):
                        print("Received stop simulation command, closing GUI...")
                        break

                    # Check if URDF path has changed (robot profile changed)
                    new_urdf_path = offline_data.get('urdf_path')
                    if new_urdf_path != current_urdf_path:
                        print(f"URDF path changed from {current_urdf_path} to {new_urdf_path}")
                        if new_urdf_path:
                            try:
                                # Remove old robot model if it exists
                                if robot_id is not None:
                                    p.removeBody(robot_id)
                                    print(f"Removed old robot model: ID = {robot_id}")

                                # Load new robot model
                                robot_id = p.loadURDF(new_urdf_path, useFixedBase=True)
                                current_urdf_path = new_urdf_path
                                print(f"Successfully loaded new robot model: ID = {robot_id}")

                                # Clear existing markers as robot has changed
                                for marker_id in marker_ids:
                                    try:
                                        p.removeUserDebugItem(marker_id)
                                    except:
                                        pass
                                marker_ids = []

                            except Exception as e:
                                print(f"Failed to reload robot model: {str(e)}")
                        else:
                            print("No URDF path provided in new offline data")

                    # Update base pose only when it actually changes
                    new_base_position = offline_data.get('base_position')
                    new_base_orientation = offline_data.get('base_orientation')

                    if new_base_position is not None and new_base_orientation is not None:
                        pos_changed = (
                            cached_base_position is None or
                            any(abs(a - b) > 1e-9 for a, b in zip(new_base_position, cached_base_position))
                        )
                        orn_changed = (
                            cached_base_orientation is None or
                            any(abs(a - b) > 1e-9 for a, b in zip(new_base_orientation, cached_base_orientation))
                        )

                        if pos_changed or orn_changed:
                            try:
                                p.resetBasePositionAndOrientation(robot_id, new_base_position, new_base_orientation)
                                cached_base_position = new_base_position[:]
                                cached_base_orientation = new_base_orientation[:]
                            except Exception as e:
                                print(f"Failed to update base pose: {str(e)}")

                    # Check for shape updates
                    updated_shapes = offline_data.get('shapes', [])
                    updated_shape_ids = set()
                    for shape in updated_shapes:
                        if shape.get('id') is not None:
                            updated_shape_ids.add(shape['id'])

                    # Check for removed shapes
                    removed_shape_ids = loaded_shape_ids - updated_shape_ids
                    for removed_id in removed_shape_ids:
                        if remove_shape_from_gui(removed_id):
                            loaded_shape_ids.remove(removed_id)

                    # Check for new shapes
                    new_shapes = []
                    for shape in updated_shapes:
                        shape_id = shape.get('id')
                        if shape_id is not None and shape_id not in loaded_shape_ids:
                            new_shapes.append(shape)
                            loaded_shape_ids.add(shape_id)

                    if new_shapes:
                        print(f"Loading {len(new_shapes)} new shapes...")
                        new_loaded_shapes = load_shapes(new_shapes, robot_id)
                        loaded_shapes.extend(new_loaded_shapes)

                        # Add pose cache for new shapes
                        for shape in new_shapes:
                            shape_id = shape.get('id')
                            if shape_id is not None:
                                params = shape.get('parameters', {})
                                shape_poses[shape_id] = {
                                    'position': params.get('position', [0, 0, 0]),
                                    'orientation': params.get('orientation', [0, 0, 0, 1])
                                }

                    # Check for pose changes in existing shapes
                    for shape in updated_shapes:
                        shape_id = shape.get('id')
                        if shape_id is not None and shape_id in loaded_shape_ids:
                            params = shape.get('parameters', {})
                            position = params.get('position')
                            orientation = params.get('orientation')

                            if position is not None and orientation is not None:
                                # Check if pose actually changed
                                cached_pose = shape_poses.get(shape_id, {})
                                cached_pos = cached_pose.get('position', [0, 0, 0])
                                cached_orn = cached_pose.get('orientation', [0, 0, 0, 1])

                                # Compare position and orientation changes (with tolerance)
                                pos_changed = any(abs(a - b) > 1e-6 for a, b in zip(position, cached_pos))
                                orn_changed = any(abs(a - b) > 1e-6 for a, b in zip(orientation, cached_orn))

                                if pos_changed or orn_changed:
                                    if update_shape_pose(shape_id, position, orientation):
                                        # Update cache
                                        shape_poses[shape_id] = {
                                            'position': position[:],
                                            'orientation': orientation[:]
                                        }

                # Check for robot state updates
                new_state = safe_get_from_queue(robot_state_queue)
                if new_state is not None:
                    # Update robot joint state
                    new_joint_angles = new_state.get('joint_angles')
                    if new_joint_angles and robot_id is not None:
                        update_robot_state(robot_id, new_joint_angles, new_state.get('tool_state'), offline_data.get('joint_config'))

                    # Update target position and orientation
                    new_target_position = new_state.get('target_position')
                    new_target_orientation = new_state.get('target_orientation')

                    if new_target_position and new_target_orientation:
                        update_tcp_markers(new_target_position, new_target_orientation)

                # Enable physics simulation stepping
                p.stepSimulation()
                time.sleep(1./60.)  # 60Hz update frequency

        except KeyboardInterrupt:
            print("GUI window closed by user.")
        finally:
            # Cleanup markers
            for marker_id in marker_ids:
                try:
                    p.removeUserDebugItem(marker_id)
                except:
                    pass

            if p.isConnected():
                p.disconnect()
            print("PyBullet GUI disconnected.")

    except Exception as e:
        print(f"Error in PyBullet GUI process: {str(e)}")
        traceback.print_exc()

    print("PyBullet GUI process terminated.")

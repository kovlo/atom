#!/usr/bin/env python

# ------------------------
#    IMPORT MODULES      #
# ------------------------
import argparse
import os
import rospkg
import subprocess
import sys
from copy import deepcopy
from datetime import date, datetime
from matplotlib import cm
import numpy
import jinja2
import yaml
from colorama import Style, Fore
import rosbag
import rospy
from urdf_parser_py.urdf import URDF
from jinja2 import Environment, FileSystemLoader

# Add displays as a function of the sensors used
from interactive_calibration.utilities import resolvePath, execute, loadConfig, uriReader, colormapToRVizColor


def create_display(display_type, options={}):
    display_dicts = {
        'rviz/Image': {'Name': 'TopCRGBDCamera-Image', 'Min Value': 0, 'Enabled': False, 'Value': False,
                       'Transport Hint': 'raw',
                       'Image Topic': '/top_center_rgbd_camera/rgb/image_raw', 'Queue Size': 2, 'Max Value': 1,
                       'Unreliable': False,
                       'Median window': 5, 'Class': 'rviz/Image', 'Normalize Range': True},
        'rviz/LaserScan': {'Min Color': '0; 0; 0', 'Style': 'Points', 'Use rainbow': True, 'Name': 'Left-LaserScan',
                           'Autocompute Intensity Bounds': True, 'Enabled': True, 'Value': True,
                           'Autocompute Value Bounds': {'Max Value': 0.5, 'Min Value': 0.5, 'Value': True},
                           'Size (m)': 0.10000000149011612, 'Unreliable': False, 'Color Transformer': 'FlatColor',
                           'Decay Time': 0, 'Size (Pixels)': 5, 'Min Intensity': 215, 'Use Fixed Frame': True,
                           'Max Intensity': 695, 'Color': '239; 41; 41', 'Invert Rainbow': False,
                           'Topic': '/left_laser/laserscan', 'Max Color': '255; 255; 255', 'Channel Name': 'intensity',
                           'Queue Size': 10, 'Position Transformer': 'XYZ', 'Alpha': 1, 'Selectable': True,
                           'Class': 'rviz/LaserScan', 'Axis': 'Z'},
        'rviz/PointCloud2': {'Min Color': '0; 0; 0', 'Style': 'Points', 'Use rainbow': True,
                             'Name': 'TopCRGBD-PointCloud2',
                             'Autocompute Intensity Bounds': True, 'Enabled': False, 'Value': False,
                             'Autocompute Value Bounds': {'Max Value': 9.872922897338867,
                                                          'Min Value': 0.9480007290840149, 'Value': True},
                             'Size (m)': 0.009999999776482582, 'Unreliable': False, 'Color Transformer': 'AxisColor',
                             'Decay Time': 0,
                             'Size (Pixels)': 3, 'Min Intensity': 0, 'Use Fixed Frame': False, 'Max Intensity': 4096,
                             'Color': '241; 225; 37', 'Invert Rainbow': False,
                             'Topic': '/top_center_rgbd_camera/depth/points',
                             'Max Color': '255; 255; 255', 'Channel Name': 'intensity', 'Queue Size': 10,
                             'Position Transformer': 'XYZ',
                             'Alpha': 1, 'Selectable': True, 'Class': 'rviz/PointCloud2', 'Axis': 'Z'},
        'rviz/Camera': {'Image Rendering': 'background and overlay', 'Name': 'TopRight-Camera', 'Enabled': False,
                        'Value': False,
                        'Overlay Alpha': 0.5, 'Transport Hint': 'raw', 'Zoom Factor': 1, 'Queue Size': 2,
                        'Visibility': {'TopCRGBDCamera-Image': True, 'TopRight-Image': True, 'TopLeft-Camera': True,
                                       'Left-LaserScan': True, 'FrontalLaser-PointCloud2': True, 'Value': True,
                                       'DataLabeler-InteractiveMarkers': False, 'RightLaser-Labels': False,
                                       'Right-LaserScan': True,
                                       'Camera': True, 'RightLaser-Clusters': True, 'LeftLaser-Clusters': True,
                                       'TopCRGBDCam-Image-Labelled': True, 'TopLeft-Image': True,
                                       'LeftLaser-Labels': False,
                                       'TopLeftImage-Labeled': True, 'FirstGuess-InteractiveMarkers': True,
                                       'RobotModel': False,
                                       'TopRightImage-Labeled': True, 'Grid': True, 'TopCRGBD-PointCloud2': True,
                                       'TF': False},
                        'Unreliable': False, 'Class': 'rviz/Camera', 'Image Topic': '/top_right_camera/image_color'},
        'rviz/InteractiveMarkers': {'Show Visual Aids': False, 'Name': 'DataLabeler-InteractiveMarkers',
                                    'Update Topic': '/data_labeler/update', 'Enabled': True, 'Show Descriptions': False,
                                    'Value': True, 'Show Axes': False, 'Enable Transparency': True,
                                    'Class': 'rviz/InteractiveMarkers'},
        'rviz/tf': {'Frame Timeout': 15, 'Name': 'TF', 'Enabled': True, 'Marker Scale': 1, 'Tree': {}, 'Value': False,
                    'Show Axes': True, 'Update Interval': 0, 'Show Names': False, 'Show Arrows': False,
                    'Frames': {'All Enabled': True}, 'Class': 'rviz/TF'},
        'rviz/grid': {'Reference Frame': 'base_footprint', 'Name': 'Grid', 'Cell Size': 1, 'Normal Cell Count': 0,
                      'Color': '160; 160; 164', 'Line Style': {'Line Width': 0.029999999329447746, 'Value': 'Lines'},
                      'Enabled': True, 'Value': True, 'Plane': 'XY', 'Offset': {'Y': 0, 'X': 0, 'Z': 0}, 'Alpha': 0.5,
                      'Plane Cell Count': 10, 'Class': 'rviz/Grid'},
        'rviz/RobotModel': {'Name': 'RobotModel', 'Links': {},
                            'Robot Description': 'robot_description', 'Visual Enabled': True, 'Enabled': True,
                            'Value': True, 'Update Interval': 0, 'Collision Enabled': False, 'TF Prefix': '',
                            'Alpha': 1, 'Class': 'rviz/RobotModel'}
    }

    d = display_dicts[display_type]
    for key in options:
        if not key in d:
            s = 'Option ' + key + ' does not exist for ' + display_type
            raise ValueError(s)

        d[key] = options[key]
    return d


if __name__ == "__main__":
    # Parse command line arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--name", help='package name', type=str, required=True)
    args = vars(ap.parse_args())

    # --------------------------------------------------------------------------
    # Initial setup
    # --------------------------------------------------------------------------
    package_name = os.path.basename(args['name'])
    rospack = rospkg.RosPack()
    interactive_calibration_path = rospack.get_path('interactive_calibration')
    rviz_set_initial_estimate = 'set_initial_estimate.rviz'
    rviz_collect_data = 'collect_data.rviz'

    # Check if package is under $ROS_PACKAGE_PATH, abort if not
    assert (package_name in rospack.list()), \
        Fore.YELLOW + package_name + ' not found under ROS. Are you sure the path you gave in under your ' \
                                     '$ROS_PACKAGE_PATH? Calibration package will not work if it is not under the ' \
                                     '$ROS_PACKAGE_PATH. Please fix this before running the package configuration. ' \
        + Style.RESET_ALL

    package_path = rospack.get_path(package_name)  # full path to the package, including its name.
    package_base_path = os.path.dirname(package_path)  # parent path where the package is located

    # Template engine setup
    file_loader = FileSystemLoader(interactive_calibration_path + '/templates')
    env = Environment(loader=file_loader, undefined=jinja2.strict_undefined)

    # Date
    dt_string = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # --------------------------------------------------------------------------
    # Read the config.yml file
    # --------------------------------------------------------------------------
    config_file = package_path + '/calibration/config.yml'
    print('Loading config file ' + config_file)
    config = loadConfig(config_file)

    # Sensors colormap. Access with:  color_map_sensors[idx, :]
    cm_sensors = cm.Set3(numpy.linspace(0, 1, len(config['sensors'].keys())))

    # --------------------------------------------------------------------------
    # Setup the description file
    # --------------------------------------------------------------------------
    description_file_in, _, _ = uriReader(config['description_file'])
    description_file_out = package_path + '/urdf/description.urdf.xacro'
    execute('ln -fs ' + description_file_in + ' ' + description_file_out,
            verbose=False)  # Create a symlink to the given xacro

    # --------------------------------------------------------------------------
    # Read the bag file
    # --------------------------------------------------------------------------
    bag_file, _, _ = uriReader(config['bag_file'])
    print('Loading bagfile ' + bag_file)
    bag = rosbag.Bag(bag_file)
    bag_info = bag.get_type_and_topic_info()
    bag_types = bag_info[0]
    bag_topics = bag_info[1]
    # print('\n' + str(bag_topics))

    # for topic, msg, t in bag.read_messages(topics=['chatter', 'numbers']):
    #     print(msg)
    bag.close()

    # --------------------------------------------------------------------------
    # Read the description.urdf.xacro file
    # --------------------------------------------------------------------------
    # Check the description file
    urdf_file = '/tmp/description.urdf'
    print('Parsing description file ' + description_file_out)
    execute('xacro ' + description_file_out + ' -o ' + urdf_file, verbose=False)  # create a temp urdf file
    try:
        description = URDF.from_xml_file(urdf_file)  # read teh urdf file
    except:
        raise ValueError('Could not parse description file ' + description_file_out)

    # print(description)
    # --------------------------------------------------------------------------
    # Verifications (run as much as we can think of to see if something is wrong)
    # --------------------------------------------------------------------------
    print('Running verifications ... please wait ...')

    compressed_topics = {}  # a list of compressed topics to decompress in the launch file
    # Check if config sensor topics exist in the bag file
    for sensor_key in config['sensors']:
        topic = config['sensors'][sensor_key]['topic_name']
        if topic not in bag_topics:

            topic_compressed = topic + '/compressed'
            if topic_compressed in bag_topics:  # Check if the topic is a compressed image topic
                msg_type = bag_info[1][topic_compressed].msg_type
                if msg_type == 'sensor_msgs/CompressedImage':  # Check if the topic of correct msg_type
                    compressed_topics[topic] = {'topic_compressed': topic_compressed, 'msg_type': msg_type,
                                                'sensor_key': sensor_key}
                    print(Fore.BLUE + 'Topic ' + topic + ' is in compressed format (' + topic_compressed +
                          '). Will setup a decompressor.' + Style.RESET_ALL)
                else:
                    raise ValueError(Fore.RED + ' Topic ' + topic + ' (from sensor ' + sensor_key +
                                     ') exists in compressed format in the bag file, but is not of msg_type '
                                     '"sensor_msgs/CompressedImage"' + Style.RESET_ALL)
            else:

                raise ValueError(Fore.RED + ' Topic ' + topic + ' (from sensor ' + sensor_key +
                                 ') does not exist in the bag file.' + Style.RESET_ALL)

    # TODO Check if config links exist in the tf topics of the bag file

    # --------------------------------------------------------------------------
    # Create the playback launch file
    # --------------------------------------------------------------------------
    playbag_launch_file = package_path + '/launch/playbag.launch'
    print('Setting up ' + playbag_launch_file + ' ...')

    template = env.get_template('playbag.launch')
    with open(playbag_launch_file, 'w') as f:
        f.write(template.render(c={'filename': os.path.basename(playbag_launch_file),
                                   'date': dt_string,
                                   'bag_file': bag_file,
                                   'package_name': package_name,
                                   'rviz_set_initial_estimate': rviz_set_initial_estimate,
                                   'use_compressed_topics': bool(compressed_topics),
                                   'compressed_topics': compressed_topics
                                   }))

    # --------------------------------------------------------------------------
    # Create the set_initial_estimate launch file
    # --------------------------------------------------------------------------
    set_initial_estimate_launch_file = package_path + '/launch/set_initial_estimate.launch'
    print('Setting up ' + set_initial_estimate_launch_file + ' ...')

    template = env.get_template(os.path.basename(set_initial_estimate_launch_file))
    with open(set_initial_estimate_launch_file, 'w') as f:
        f.write(template.render(c={'filename': os.path.basename(set_initial_estimate_launch_file),
                                   'date': dt_string,
                                   'package_name': package_name,
                                   'rviz_set_initial_estimate': rviz_set_initial_estimate,
                                   }))

    # --------------------------------------------------------------------------
    # Create the data collection launch file
    # --------------------------------------------------------------------------
    data_collection_launch_file = package_path + '/launch/collect_data.launch'
    print('Setting up ' + data_collection_launch_file + ' ...')

    template = env.get_template(os.path.basename(data_collection_launch_file))
    with open(data_collection_launch_file, 'w') as f:
        f.write(template.render(c={'filename': os.path.basename(set_initial_estimate_launch_file),
                                   'date': dt_string,
                                   'package_name': package_name,
                                   'rviz_collect_data': rviz_collect_data,
                                   }))

    # --------------------------------------------------------------------------
    # Create the rviz config core displays (used in several rviz config files)
    # --------------------------------------------------------------------------
    # TODO change rviz fixed_frame according to args['world_link']
    core_displays = []

    # Create grid, tf and robot model displays
    rendered = env.get_template('/rviz/Grid.rviz').render(c={'Reference_Frame': config['world_link']})
    core_displays.append(yaml.load(rendered, Loader=yaml.SafeLoader))

    rendered = env.get_template('/rviz/TF.rviz').render(c={'Name': 'TF'})
    core_displays.append(yaml.load(rendered, Loader=yaml.SafeLoader))

    rendered = env.get_template('/rviz/RobotModel.rviz').render(c={'Name': 'RobotModel'})
    core_displays.append(yaml.load(rendered, Loader=yaml.SafeLoader))

    # --------------------------------------------------------------------------
    # Create the rviz config file for the set_initial_estimate
    # --------------------------------------------------------------------------
    rviz_file_template = interactive_calibration_path + '/templates/config.rviz'
    print('Setting up ' + rviz_set_initial_estimate + ' ...')
    rviz = yaml.load(open(rviz_file_template), Loader=yaml.SafeLoader)
    displays = core_displays  # start with the core displays

    # Create interactive marker display for moving the sensors
    rendered = env.get_template('/rviz/InteractiveMarker.rviz').render(c={'Name': 'MoveSensors-InteractiveMarker',
                                                                          'Update_Topic': 'set_initial_estimate/update'}
                                                                       )
    displays.append(yaml.load(rendered, Loader=yaml.SafeLoader))

    # Generate rviz displays according to the sensor types
    for idx, sensor_key in enumerate(config['sensors']):
        color = colormapToRVizColor(cm_sensors[idx, :])
        topic = config['sensors'][sensor_key]['topic_name']
        topic_compressed = topic + '/compressed'
        if topic in bag_topics:
            msg_type = bag_info[1][topic].msg_type
        else:
            msg_type = bag_info[1][topic_compressed].msg_type

        print('\tGenerating rviz displays for sensor ' + sensor_key + ' with topic ' + topic + ' (' + msg_type + ')')

        if msg_type == 'sensor_msgs/CompressedImage' or \
                msg_type == 'sensor_msgs/Image':  # add displays for camera sensor

            # Raw image
            rendered = env.get_template('/rviz/Image.rviz').render(c={'Name': sensor_key + '-Image',
                                                                      'Image_Topic': topic})
            displays.append(yaml.load(rendered, Loader=yaml.SafeLoader))

            # Camera
            rendered = env.get_template('/rviz/Camera.rviz').render(c={'Name': sensor_key + '-Camera',
                                                                       'Image_Topic': topic})
            displays.append(yaml.load(rendered, Loader=yaml.SafeLoader))

        elif msg_type == 'sensor_msgs/LaserScan':

            # Raw data
            rendered = env.get_template('/rviz/LaserScan.rviz').render(c={'Name': sensor_key + '-LaserScan',
                                                                          'Topic': topic,
                                                                          'Color': color})
            displays.append(yaml.load(rendered, Loader=yaml.SafeLoader))

        elif msg_type == 'sensor_msgs/PointCloud2':

            # Raw data
            rendered = env.get_template('/rviz/PointCloud2.rviz').render(c={'Name': sensor_key + '-PointCloud2',
                                                                            'Topic': topic,
                                                                            'Color': color,
                                                                            'Style': 'Points',
                                                                            'Size__m_': 0.2,
                                                                            'Alpha': 1})
            displays.append(yaml.load(rendered, Loader=yaml.SafeLoader))

        else:
            print(Fore.YELLOW + 'Warning: Cannot generate rviz configuration for sensor ' + sensor_key + ' with topic '
                  + topic + ' (' + msg_type + ')' + Style.RESET_ALL)

    rviz['Visualization Manager']['Displays'] = displays
    yaml.dump(rviz, open(package_path + '/rviz/' + rviz_set_initial_estimate, 'w'))

    # --------------------------------------------------------------------------
    # Create the rviz config file for the collect_data
    # --------------------------------------------------------------------------
    # TODO continue here
    rviz_file_template = interactive_calibration_path + '/templates/config.rviz'
    print('Setting up ' + rviz_collect_data + ' ...')
    rviz = yaml.load(open(rviz_file_template), Loader=yaml.FullLoader)
    displays = core_displays  # start with the core displays

    # Add interactive maker display to handle sensor manual labeling
    displays.append(create_display('rviz/InteractiveMarkers', {'Name': 'ManualDataLabeler-InteractiveMarkers',
                                                               'Update Topic': 'data_labeler/update'}))

    cm_sensors = cm.Set3(numpy.linspace(0, 1, len(config['sensors'].keys())))  # Access with:  color_map_sensors[idx, :]

    # Generate rviz displays according to the sensor types
    for idx, sensor_key in enumerate(config['sensors']):
        topic = config['sensors'][sensor_key]['topic_name']
        topic_compressed = topic + '/compressed'
        if topic in bag_topics:
            msg_type = bag_info[1][topic].msg_type
        elif topic_compressed in bag_topics:
            msg_type = bag_info[1][topic_compressed].msg_type
        else:
            raise ValueError('Could not find topic ' + topic + ' in bag file.')

        print('\tGenerating rviz displays for sensor ' + sensor_key + ' with topic ' + topic + ' (' + msg_type + ')')

        if msg_type == 'sensor_msgs/CompressedImage' or msg_type == 'sensor_msgs/Image':  # add displays for camera sensor

            display_name = sensor_key + '-Image'

            # Raw data Image
            displays.append(
                create_display('rviz/Image', {'Name': display_name, 'Image Topic': topic, 'Enabled': False}))

            # Labeled data Image
            display_name = sensor_key + '-Labels' + '-Image'
            displays.append(create_display('rviz/Image', {'Name': display_name, 'Image Topic': topic + '/labeled',
                                                          'Enabled': False}))
            # Camera
            display_name = sensor_key + '-Camera'
            displays.append(
                create_display('rviz/Camera', {'Name': display_name, 'Image Topic': topic, 'Enabled': False}))

        elif msg_type == 'sensor_msgs/LaserScan':

            display_name = sensor_key + '-LaserScan'
            color = str(int(cm_sensors[idx, 0] * 255)) + '; ' + str(int(cm_sensors[idx, 1] * 255)) + '; ' + \
                    str(int(cm_sensors[idx, 2] * 255))

            # Raw data
            displays.append(deepcopy(create_display('rviz/LaserScan',
                                                    {'Name': display_name, 'Topic': topic, 'Enabled': True,
                                                     'Color': color})))
            wg[display_name] = {'collapsed': True}

            # Data labels
            display_name = sensor_key + '-Labels-PointCloud2'
            displays.append(deepcopy(create_display('rviz/PointCloud2',
                                                    {'Name': display_name, 'Topic': topic + '/labeled', 'Enabled': True,
                                                     'Color': color, 'Style': 'Spheres', 'Size (m)': 0.2,
                                                     'Alpha': 0.05})))

            wg[display_name] = {'collapsed': True}

            # TODO Data clusters

        elif msg_type == 'sensor_msgs/PointCloud2':

            display_name = sensor_key + '-PointCloud2'
            color = str(int(cm_sensors[idx, 0] * 255)) + '; ' + str(int(cm_sensors[idx, 1] * 255)) + '; ' + str(
                int(cm_sensors[idx, 2] * 255))

            # Raw data
            displays.append(deepcopy(create_display('rviz/PointCloud2',
                                                    {'Name': display_name, 'Topic': topic, 'Enabled': True,
                                                     'Color': color, 'Style': 'Points', 'Size (m)': 0.2,
                                                     'Alpha': 1})))

            # Labeled data
            display_name = sensor_key + '-Labels-PointCloud2'
            displays.append(deepcopy(create_display('rviz/PointCloud2',
                                                    {'Name': display_name, 'Topic': topic + '/labeled', 'Enabled': True,
                                                     'Color': color, 'Style': 'Spheres', 'Size (m)': 0.2,
                                                     'Alpha': 0.05})))
        else:
            print(Fore.YELLOW + 'Warning: Cannot generate rviz configuration for sensor ' + sensor_key + ' with topic '
                  + topic + ' (' + msg_type + ')' + Style.RESET_ALL)

    rviz['Visualization Manager']['Displays'] = displays
    yaml.dump(rviz, open(package_path + '/rviz/' + rviz_collect_data, 'w'))

    # Print final message
    print(
            '\nSuccessfully configured calibration package ' + Fore.BLUE + package_name + Style.RESET_ALL + '. You can use the launch files:')
    print(Fore.BLUE + 'roslaunch ' + package_name + ' ' + os.path.basename(playbag_launch_file) + Style.RESET_ALL)
    print(Fore.BLUE + 'roslaunch ' + package_name + ' ' + os.path.basename(
        set_initial_estimate_launch_file) + Style.RESET_ALL)
    print(Fore.BLUE + 'roslaunch ' + package_name + ' ' + os.path.basename(
        data_collection_launch_file) + Style.RESET_ALL)

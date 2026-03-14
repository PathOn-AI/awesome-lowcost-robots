import cv2
import numpy as np

img = cv2.imread('your_marker.png')

# Try all common dictionaries
dicts_to_try = {
    'DICT_4X4_50'  : cv2.aruco.DICT_4X4_50,
    'DICT_5X5_50'  : cv2.aruco.DICT_5X5_50,
    'DICT_6X6_50'  : cv2.aruco.DICT_6X6_50,
}

for name, dict_id in dicts_to_try.items():
    aruco_dict   = cv2.aruco.getPredefinedDictionary(dict_id)
    aruco_params = cv2.aruco.DetectorParameters()
    detector     = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

    corners, ids, _ = detector.detectMarkers(img)

    if ids is not None:
        print(f'✅ Found! Dictionary: {name}, ID: {ids.flatten()}')
    else:
        print(f'❌ Not found in {name}')

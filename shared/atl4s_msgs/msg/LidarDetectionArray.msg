# A frame's worth of lidar detections. The header's `stamp` and `frame_id`
# anchor every Detection in the array — individual entries' own headers
# can be left empty or copied for downstream convenience.

std_msgs/Header header
LidarDetection[] detections

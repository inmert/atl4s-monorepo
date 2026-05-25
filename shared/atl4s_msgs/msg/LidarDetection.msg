# A single object detected in a lidar scan. Coordinate frame is set on the
# enclosing LidarDetectionArray's header (usually the lidar's sensor frame).

std_msgs/Header header

# Class label from the producer (e.g. "aircraft", "tank", "other").
string class_id

# Confidence in [0.0, 1.0]. Classical clusterers populate this with a
# geometry-fit heuristic; learned models populate it with the softmax of
# their final layer.
float32 score

# Centroid of the detection in the sensor frame.
geometry_msgs/Point center

# Axis-aligned bounding box dimensions: x = length, y = width, z = height.
geometry_msgs/Vector3 size

# Tracker id. 0 when no tracker is attached (single-frame detection).
int32 track_id

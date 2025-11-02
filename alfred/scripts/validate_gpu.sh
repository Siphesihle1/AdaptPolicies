#!/bin/bash

DEVICE_QUERY_FILE=$1

# Extract information from deviceQuery output
query_num_devices=$(grep "Detected" "$DEVICE_QUERY_FILE" | grep -o '[0-9]\+')
query_device_name=$(grep "Device [0-9]\+:" "$DEVICE_QUERY_FILE" | sed 's/Device [0-9]\+: "\(.*\)"/\1/')

# Get information from nvidia-smi
smi_num_devices=$(nvidia-smi --list-gpus | wc -l)
smi_device_name=$(nvidia-smi --query-gpu=gpu_name --format=csv,noheader)

# Compare results
if [ "$query_num_devices" != "$smi_num_devices" ]; then
    echo "Number of devices mismatch:"
    echo "  deviceQuery: $query_num_devices"
    echo "  nvidia-smi: $smi_num_devices"
    exit 1
fi

if [ "$query_device_name" != "$smi_device_name" ]; then
    echo "Device name mismatch:"
    echo "  deviceQuery: $query_device_name"
    echo "  nvidia-smi: $smi_device_name"
    exit 1
fi

echo "GPU validation passed!"
echo -e "Found $query_num_devices device(s): \n$query_device_name"
exit 0

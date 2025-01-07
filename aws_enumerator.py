#!/usr/bin/env python3

import sys
from PySide6 import QtWidgets, QtCore, QtGui
import boto3
from botocore.exceptions import ClientError

def get_all_resources():
    """
    Enumerate AWS resources across all regions and return them in a dictionary, keyed by region.
    """
    import boto3  # ensure Boto3 is imported here if needed

    resources_by_region = {}
    ec2_client = boto3.client('ec2')
    try:
        regions_data = ec2_client.describe_regions()
        regions = [r['RegionName'] for r in regions_data['Regions']]
    except ClientError as e:
        # For the GUI, we can still return partial info or handle the exception
        return {}

    # Include a special 'ALL' region label
    regions.insert(0, 'ALL')

    for region in regions:
        if region == 'ALL':
            # We'll skip enumerating this placeholder
            continue

        region_data = {
            'Instances': [],
            'Volumes': [],
            'Snapshots': [],
            'SecurityGroups': [],
            'S3Buckets': [],
            'RDSInstances': []
        }

        try:
            ec2 = boto3.client('ec2', region_name=region)
            # Instances
            instances_data = ec2.describe_instances()
            for reservation in instances_data['Reservations']:
                for instance in reservation['Instances']:
                    region_data['Instances'].append(instance['InstanceId'])

            # Volumes
            volumes_data = ec2.describe_volumes()
            for volume in volumes_data['Volumes']:
                region_data['Volumes'].append(volume['VolumeId'])

            # Snapshots
            snapshots_data = ec2.describe_snapshots(OwnerIds=['self'])
            for snapshot in snapshots_data['Snapshots']:
                region_data['Snapshots'].append(snapshot['SnapshotId'])

            # Security Groups
            sgs_data = ec2.describe_security_groups()
            for sg in sgs_data['SecurityGroups']:
                region_data['SecurityGroups'].append(f"{sg['GroupName']} ({sg['GroupId']})")

        except ClientError as e:
            # Handle or log errors
            pass

        # S3 (global, we just store if it matches current region)
        try:
            s3_client = boto3.client('s3')
            buckets_data = s3_client.list_buckets()
            for bucket in buckets_data['Buckets']:
                bucket_region = s3_client.get_bucket_location(Bucket=bucket['Name'])['LocationConstraint']
                if bucket_region == region or (bucket_region is None and region == 'us-east-1'):
                    region_data['S3Buckets'].append(bucket['Name'])
        except ClientError:
            pass

        # RDS
        try:
            rds = boto3.client('rds', region_name=region)
            rds_data = rds.describe_db_instances()
            for db_instance in rds_data['DBInstances']:
                region_data['RDSInstances'].append(
                    f"{db_instance['DBInstanceIdentifier']} (Status: {db_instance['DBInstanceStatus']})"
                )
        except ClientError:
            pass

        resources_by_region[region] = region_data

    return resources_by_region


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AWS Enumerator Tool")
        self.resize(1000, 600)

        # Main Widget and Layout
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # A splitter for top area (regions on left, resources on right)
        top_splitter = QtWidgets.QSplitter()
        top_splitter.setOrientation(QtCore.Qt.Horizontal)
        main_layout.addWidget(top_splitter)

        # Bottom log pane
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)

        # Left side: region list
        self.region_list = QtWidgets.QListWidget()
        self.region_list.setFixedWidth(200)
        top_splitter.addWidget(self.region_list)

        # Right side: resources display
        self.resource_display = QtWidgets.QTextEdit()
        self.resource_display.setReadOnly(True)
        top_splitter.addWidget(self.resource_display)

        # Fetch all resource data from AWS
        self.resources = get_all_resources()

        # Populate the region list (including 'ALL')
        for region in sorted(self.resources.keys()):
            self.region_list.addItem(region)

        # Connect region list selection to display update
        self.region_list.currentItemChanged.connect(self.display_resources_for_region)

        # Initial log message
        self.log("AWS Enumerator initialized. Select a region on the left to see its resources.")

    def display_resources_for_region(self, current, previous):
        if not current:
            return

        region = current.text()
        if region == "ALL":
            # Combine data for all regions
            combined = {
                'Instances': [],
                'Volumes': [],
                'Snapshots': [],
                'SecurityGroups': [],
                'S3Buckets': [],
                'RDSInstances': []
            }
            for r, region_data in self.resources.items():
                if r == "ALL":
                    continue
                for key in combined:
                    combined[key].extend(region_data[key])

            self.log(f"Displaying resources for ALL regions.")
            self.resource_display.clear()
            self.resource_display.append(self.format_region_data("ALL", combined))
        else:
            region_data = self.resources.get(region, {})
            self.log(f"Displaying resources for region {region}.")
            self.resource_display.clear()
            self.resource_display.append(self.format_region_data(region, region_data))

    def format_region_data(self, region, data_dict):
        lines = [f"Resources in region: {region}\n"]
        for resource_type, items in data_dict.items():
            lines.append(f"{resource_type}:")
            if not items:
                lines.append("  - (none)")
            else:
                for item in items:
                    lines.append(f"  - {item}")
            lines.append("")
        return "\n".join(lines)

    def log(self, message):
        self.log_text.append(message)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

# Remove the old "if __name__ == '__main__': main()" that enumerated in console
# and replace it with the new PyQt launch:
if __name__ == "__main__":
    main() 
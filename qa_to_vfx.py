import argparse
import math
import ffmpeg
import openpyxl.drawing
import openpyxl.drawing.image
import pymongo
import pandas as pd  # Need openpyxl for excel
import re
import os
import openpyxl
import vimeo
from dotenv import load_dotenv


# Output unused frames to CSV
def output_unused():
    print("Exporting unused frames to csv...")
    query_docs = mydb["baselight"].find({"frames": {"$gt": vid_frames}}).to_list()

    result = []

    if query_docs:  # Continue if query not empty
        for doc in query_docs:
            within_vid = [x for x in doc["frames"] if x > vid_frames]
            grouped_frames = group_by_range(within_vid)
            result.append({"location": doc["location"], "frames": grouped_frames})

    matched_locations = match_xytech_locations(result)
    timecoded_list = frame_range_to_timecodes(matched_locations)
    outputted_list = format_output(timecoded_list)

    out_df = pd.DataFrame(outputted_list)
    out_df.to_csv("unused_frames.csv", index=False)

    print("Finished exporting unused frames csv!")


def timecode_to_duration(timecode):
    time_list = timecode.split(":")
    return ":".join(time_list[:3])


# Render and upload to Vimeo
def render_and_upload(input_list):
    print("Rendering and uploading videos...")
    counter = 0
    if not os.path.exists("videos"):
        os.makedirs("videos")

    # Render out video
    for x in input_list:
        frames = x["Frame Range"].split("-")
        start_frame = int(frames[0])
        end_frame = int(frames[1])

        start = start_frame / vid_fps
        end = end_frame / vid_fps
        vid_title = f"render_vid_{counter}.mp4"
        output_path = os.path.join("videos", vid_title)

        out_stream = ffmpeg.input(args.process, ss=start, to=end)
        out_stream = out_stream.output(
            output_path, vcodec="libx264", pix_fmt="yuv420p", vframes=1
        ).overwrite_output()
        ffmpeg.run(out_stream, capture_stderr=True, capture_stdout=True)
        counter += 1

    # Setting up Vimeo client
    load_dotenv()
    access_token = os.getenv("ACCESS_TOKEN")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    vim_client = vimeo.VimeoClient(
        token=access_token, key=client_id, secret=client_secret
    )

    for vid in os.listdir("videos"):
        vid_path = os.path.join("videos", vid)
        vim_client.upload(vid_path, data={"name": vid, "description": vid})
    print("Finished uploading rendered videos!")


# Add thumbnail column to excel
def add_thumbnail():
    print("Inserting thumbnails to excel sheet...")
    excel_df = pd.read_excel("output.xlsx")
    excel_df["Thumbnails"] = None  # Add Thumbnails column
    excel_df.to_excel("output.xlsx", index=False)
    images_list = []
    if not os.path.exists("thumbnails"):
        os.makedirs("thumbnails")
    for row in excel_df.itertuples(index=True, name="Sheet1"):
        frame_range = row._2  # Frame Range column
        output_path = os.path.join("thumbnails", f"{row.Index}.png")
        frames = frame_range.split("-")
        start_frame = int(frames[0])
        end_frame = int(frames[1])

        mid_frame = round((start_frame + end_frame) / 2)
        mid_timecode = frame_to_timecode(mid_frame, vid_fps)
        duration_format = timecode_to_duration(mid_timecode)

        out_thumb = ffmpeg.input(args.process, ss=duration_format)
        out_thumb = out_thumb.filter("scale", 96, 74)
        out_thumb = out_thumb.output(
            output_path, vframes=1, update=1
        ).overwrite_output()
        ffmpeg.run(out_thumb, capture_stderr=True, capture_stdout=True)
        images_list.append(output_path)

    # Insert images to excel
    wrkb = openpyxl.load_workbook("output.xlsx")
    sheet = wrkb.active
    sheet["A1"]
    for i in range(len(images_list)):
        img = openpyxl.drawing.image.Image(images_list[i])
        sheet.add_image(img, f"D{2 + i}")
    wrkb.save("output.xlsx")
    print("Finished inserting images!")


# Format list to correct format for exporting to XLSX
def format_output(input_list):
    print("Formatting list for output...")
    results = []
    for i in input_list:
        location = i["location"]
        frame_ranges = i["frames"]
        timecode_ranges = i["timecodes"]
        for f in range(len(frame_ranges)):
            frames = frame_ranges[f]
            timecodes = timecode_ranges[f]
            if len(frames) == 2:
                frame_str = f"{frames[0]}-{frames[1]}"
                time_str = f"{timecodes[0]}-{timecodes[1]}"
            else:
                frame_str = frames[0]
                time_str = timecodes[0]
            results.append(
                {
                    "Location": location,
                    "Frame Range": frame_str,
                    "Timecode Range": time_str,
                }
            )
    print("Finished formatting list!")
    return results


# Convert frame ranges into timecode ranges
def frame_range_to_timecodes(input_list):
    print("Converting frame ranges to timecode ranges...")
    for b in input_list:
        timecodes = []
        for frames in b["frames"]:
            start_timecode = frame_to_timecode(frames[0], vid_fps)
            if len(frames) == 2:
                end_timecode = frame_to_timecode(frames[1], vid_fps)
                timecodes.append([start_timecode, end_timecode])
            else:
                timecodes.append([start_timecode])
        b["timecodes"] = timecodes
    print("Finished converting range frames to timecodes!")
    return input_list


# Match Baselight locations with Xytech locations in db, return list with proper locations
def match_xytech_locations(baselight_list):
    print("Finding Xytech location match...")
    results = []
    for b in baselight_list:
        search_str = re.search(r"(/dogman.*)", b["location"]).group(
            1
        )  # Extracts only dogman part
        xytech_location = mydb["xytech"].find_one({"location": {"$regex": search_str}})[
            "location"
        ]
        results.append({"location": xytech_location, "frames": b["frames"]})
    print("Replaced Baselight with proper Xytech locations!")
    return results


# Find Baselight ranges that are within video length by comparing frames
def find_ranges_in_vid_length(vid_frames):
    print("Querying Baselight docs within video frames...")
    result = []
    query_docs = mydb["baselight"].find({"frames": {"$lte": vid_frames}}).to_list()

    if query_docs:  # Continue if query not empty
        for doc in query_docs:
            within_vid = [x for x in doc["frames"] if x <= vid_frames]
            grouped_frames = group_by_range(within_vid)
            ranged_frames = [
                x for x in grouped_frames if len(x) == 2
            ]  # Filter for ranged frames ([start, end])
            result.append({"location": doc["location"], "frames": ranged_frames})
    print("Finished query and processing of Baselight frames!")
    return result


# Extract video file timecode and total frames
def extract_timecode_and_frames(video):
    print("Extracting video timecode and frames...")
    video_metadata = ffmpeg.probe(video)["streams"][0]  # First index is video metadata
    fps_fraction = video_metadata["avg_frame_rate"]
    total_frames = int(video_metadata["nb_frames"])

    # Convert fps fraction to fps
    numerator, denominator = fps_fraction.split("/")
    fps = round(int(numerator) / int(denominator), 2)
    video_timecode = frame_to_timecode(total_frames, fps)
    print("Finished extracting video timecode and frames!")
    return video_timecode, total_frames, fps


# Convert frame to timecode by specified fps
def frame_to_timecode(frame, fps):
    total_seconds = math.floor(frame / fps)

    hours = math.floor(total_seconds / 3600)
    remainder_seconds = total_seconds % 3600
    minutes = math.floor(remainder_seconds / 60)
    seconds = remainder_seconds % 60
    extra_frames = math.floor(frame % fps)  # Don't consider non-whole frames

    timecode = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{extra_frames:02d}"

    return timecode


# Process Xytech file
def process_xytech():
    results = []
    found_locations = False
    workorder = None
    print("Processing Xytech...")
    with open(args.xytech, "r") as f:
        for line in f:
            line = line.strip()

            # Found workorder number
            if "Xytech Workorder" in line:
                match = re.search(r"Xytech Workorder\s+(\d+)", line)
                if match:
                    workorder = match.group(1)
                continue

            # Found start of locations
            if "Location:" in line:
                found_locations = True
                continue

            # End of locations
            if found_locations and (line == "Notes:" or not line.startswith("/hpsans")):
                found_locations = False
                # Ensures doesn't stop if theres in empty line gap between locations
                if not line.startswith("/hpsans"):
                    continue

            # Get location and append to results
            if found_locations and line.startswith("/hpsans"):
                results.append(
                    {
                        "workorder": workorder,
                        "location": line,
                    }
                )
    print("Xytech process finished!")
    return results


# Group frames by range if frames are less than video frames
def group_by_range(frames):
    res = []
    start = frames[0]
    end = -1
    counter = start + 1
    for x in frames[1::]:
        if x == counter:  # Number is consecutive
            end = x
            counter += 1
        else:  # Number not consecutive, end of range
            if end != -1:
                res.append([start, end])
                end = -1
            else:
                res.append([start])
            start = x
            counter = start + 1
    # End of list reached
    if end != -1:
        res.append([start, end])
    else:
        res.append([start])
    return res


# Process baselight file and group frames by location
def process_baselight():
    results = []
    print("Processing Baselight...")
    with open(args.baselight, "r") as f:
        for line in f:
            if not line.strip():  # Ignore newline chars
                continue
            location = line.split()[0]  # First index is location
            all_frames = line.split()[
                1:
            ]  # Second index to end of line are frames, already sorted

            frames_arr = [int(x) for x in all_frames]
            if not results:  # Empty results, first insert
                results.append({"location": location, "frames": frames_arr})
            else:
                index = next(
                    (i for i, x in enumerate(results) if x["location"] == location),
                    None,
                )
                if index is None:  # New location being added
                    results.append({"location": location, "frames": frames_arr})
                else:
                    results[index]["frames"].extend(frames_arr)

    print("Baselight process finished!")
    return results


# Process arguments
parser = argparse.ArgumentParser(
    description="Upload baselight and xytech to MongoDB and extract frames within length of video"
)
parser.add_argument(
    "--baselight", metavar="TXT_FILE", type=str, help="Path to Baselight text file"
)
parser.add_argument(
    "--xytech", metavar="TXT_FILE", type=str, help="Path to Xytech text file"
)
parser.add_argument(
    "--process", metavar="VIDEO_FILE", type=str, help="Path to video to process"
)
parser.add_argument(
    "--output",
    action="store_true",
    help="Optional to output frames with thumbnails, location, timecode in XLSX format",
)
args = parser.parse_args()


# Get MongoDB client and database
myclient = pymongo.MongoClient(
    "mongodb+srv://${MONGODB_USER}:${MONGODB_PASS}@467chaja.aslhy.mongodb.net/?retryWrites=true&w=majority&appName=467Chaja"
)
mydb = myclient["467-proj4"]

# Upload to MongoDB
if args.xytech:
    print(f"Xytech received: {args.xytech}")
    mydb["xytech"].drop()
    results = process_xytech()
    mydb["xytech"].insert_many(results)
    print("Uploaded Xytech to db!")
if args.baselight:
    print(f"Baselight received: {args.baselight}")
    mydb["baselight"].drop()
    results = process_baselight()
    mydb["baselight"].insert_many(results)
    print("Uploaded Baselight to db!")
if args.process:
    print(f"Video file received: {args.process}")
    vid_timecode, vid_frames, vid_fps = extract_timecode_and_frames(args.process)
    baselight_frames = find_ranges_in_vid_length(vid_frames)
    if args.output:
        matched_frames = match_xytech_locations(baselight_frames)
        updated_list = frame_range_to_timecodes(matched_frames)
        output_list = format_output(updated_list)

        # Export list to excel
        output_df = pd.DataFrame(output_list)
        output_df.to_excel("output.xlsx", index=False)
        add_thumbnail()
        render_and_upload(output_list)
        output_unused()

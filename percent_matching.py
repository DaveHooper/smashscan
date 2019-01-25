import time
import cv2
import numpy as np

# SmashScan Libraries
import util
import timeline

# An object that takes a capture and a number of input parameters and performs
# a number of template matching operations. Parameters include a step_size for
# the speed of iteration, frame_range for the range of frame numbers to be
# surveyed, gray_flag for a grayscale or BGR analysis, roi_flag for only a
# sub-image (region of interest) to be searched, show_flag which displays
# results with cv2.imshow(), and wait_flag which waits between frames.
class PercentMatcher:

    def __init__(self, capture, step_size=60, frame_range=None,
        num_init_frames=60, gray_flag=True, show_flag=False, wait_flag=False):

        self.capture = capture
        self.step_size = step_size
        self.num_init_frames = num_init_frames
        self.gray_flag = gray_flag
        self.show_flag = show_flag

        # Predetermined parameters that have been tested to work best.
        self.roi_flag = True
        self.template_match_radius = 2
        self.conf_threshold = 0.8
        self.calib_w_range = (24, 30)
        self.roi_y_tolerance = 3
        self.prec_step_size = 2
        self.prec_step_threshold = 4

        # Paramaters that are redefined later on during initialization.
        self.template_roi = None

        # Set the start/stop frame to the full video if frame_range undefined.
        if frame_range:
            self.start_fnum, self.stop_fnum = frame_range
        else:
            self.start_fnum = 0
            self.stop_fnum = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        # Set the wait_length for cv2.waitKey. 0 represents waiting, 1 = 1ms.
        if wait_flag:
            self.wait_length = 0
        else:
            self.wait_length = 1

        # Read the percentage sign image file and extract a binary mask based
        # off of the alpha channel. Also, resize to the 360p base height.
        self.orig_pct_img, self.orig_pct_mask = get_image_and_mask(
            "resources/pct.png", gray_flag)
        self.pct_img, self.pct_mask = resize_image_and_mask(
            self.orig_pct_img, self.orig_pct_mask, 360/480)


    def __del__(self):
        self.capture.release()
        cv2.destroyAllWindows()


    #### PERCENT MATCHER TESTS ################################################

    # Run the sweep template matching test over a video range.
    def sweep_test(self):

        # Iterate through video range and use cv2 to perform template matching.
        start_time = time.time()
        for fnum in range(self.start_fnum, self.stop_fnum, self.step_size):

            # Obtain the frame and get the template confidences and locations.
            frame = util.get_frame(self.capture, fnum, self.gray_flag)
            confidence_list, bbox_list = self.get_tm_results(frame, 4)

            # Display frame with a confidence label if show_flag is enabled.
            if self.show_flag:
                label_list = ["{:0.3f}".format(i) for i in confidence_list]
                label = " ".join(label_list)
                util.show_frame(frame, bbox_list, text=label)
                if cv2.waitKey(self.wait_length) & 0xFF == ord('q'):
                    break

        # Display the time taken to complete the test.
        frame_count = (self.stop_fnum - self.start_fnum) // self.step_size
        util.display_fps(start_time, frame_count)


    # Run the calibrate template test over a video range.
    def calibrate_test(self):

        # Iterate through video range and use cv2 to perform template matching.
        start_time = time.time()
        for fnum in range(self.start_fnum, self.stop_fnum, self.step_size):

            # Obtain the frame and get the calibrated template size.
            frame = util.get_frame(self.capture, fnum, self.gray_flag)
            bbox, opt_conf, opt_w, opt_h = self.get_calibrate_results(frame)

            # Get the percent sign accuracy according to the default (480, 584)
            # to (360, 640) rescale change from (24, 32) to (18, 24).
            orig_conf_list, _ = self.get_tm_results(frame, 1)

            # Display frame with a confidence label if show_flag is enabled.
            if self.show_flag:
                label = "({}, {}) {:0.3f} -> {:0.3f}".format(
                    opt_w, opt_h, orig_conf_list[0], opt_conf)
                util.show_frame(frame, bbox_list=[bbox], text=label)
                if cv2.waitKey(self.wait_length) & 0xFF == ord('q'):
                    break

        # Display the time taken to complete the test.
        frame_count = (self.stop_fnum - self.start_fnum) // self.step_size
        util.display_fps(start_time, frame_count)


    # Run the initialize template test over a number of random frames.
    def initialize_test(self):

        # Generate random frames to search for a proper template size.
        start_time = time.time()
        random_fnum_list = np.random.randint(low=self.start_fnum,
            high=self.stop_fnum, size=self.num_init_frames)
        opt_w_list, bbox_list = list(), list()

        for random_fnum in random_fnum_list:

            # Get the calibrated accuracy, and get the original accuracy
            # according to the default (24, 32) to (18, 24) rescale.
            frame = util.get_frame(self.capture, random_fnum, self.gray_flag)
            bbox, opt_conf, opt_w, opt_h = self.get_calibrate_results(frame)
            orig_conf_list, _ = self.get_tm_results(frame, 1)

            # Store the template width if above a confidence threshold.
            if opt_conf > self.conf_threshold:
                opt_w_list.append(opt_w)
                bbox_list.append(bbox)
                print((opt_w, opt_h), bbox, random_fnum, opt_conf)

            # Display frame with a confidence label if show_flag is enabled.
            if self.show_flag:
                label = "({}, {}) {:0.3f} -> {:0.3f}".format(
                    opt_w, opt_h, orig_conf_list[0], opt_conf)
                util.show_frame(frame, bbox_list=[bbox], text=label)
                if cv2.waitKey(self.wait_length) & 0xFF == ord('q'):
                    break

        # Display the optimal bbox and time taken to complete the test.
        opt_w = int(np.median(opt_w_list))
        h, w = self.pct_img.shape[:2]
        self.template_roi = self.get_template_roi(bbox_list)
        print("Optimal Template Size: ({}, {})".format(opt_w, h*opt_w//w))
        print("Optimal ROI bbox: {}".format(self.template_roi))
        util.display_fps(start_time, self.num_init_frames)
        util.show_frame(frame, bbox_list=[self.template_roi], wait_flag=True)


    # Run the timeline template test over a video range.
    def timeline_test(self):

        # Use a random number of frames to calibrate the percent template size.
        start_time = time.time()
        self.initialize_template_scale()
        util.display_fps(start_time, self.num_init_frames, "Initialize")

        # Iterate through the video to identify when percent is present.
        start_time = time.time()
        pct_timeline = self.get_pct_timeline()
        frame_count = (self.stop_fnum - self.start_fnum) // self.step_size
        util.display_fps(start_time, frame_count, "Initial Sweep")

        # Fill holes in the history timeline list, and filter out timeline
        # sections that are smaller than a particular size.
        clean_timeline = timeline.fill_filter(pct_timeline)
        clean_timeline = timeline.size_filter(clean_timeline, self.step_size)
        if self.show_flag:
            timeline.show_plots(pct_timeline, clean_timeline, ["pct found"])

        # Display the frames associated with the calculated match ranges.
        timeline_ranges = timeline.get_ranges(clean_timeline)
        match_ranges = np.multiply(timeline_ranges, self.step_size)
        if self.show_flag:
            util.show_frames(self.capture, match_ranges.flatten())

        # Display the frames associated with the precise match ranges.
        start_time = time.time()
        new_match_ranges = self.get_precise_match_ranges(match_ranges)
        util.display_fps(start_time, 0, "Cleaning Sweep")
        print("\tMatch Ranges: {:}".format(match_ranges.tolist()))
        print("\tPrecise Match Ranges: {:}".format(new_match_ranges.tolist()))
        if self.show_flag:
            util.show_frames(self.capture, new_match_ranges.flatten())
        return new_match_ranges


    #### PERCENT MATCHER HELPER METHODS #######################################

    # Given a frame, return a confidence list and bounding box list.
    def get_tm_results(self, frame, num_results):

        # If the template ROI has been initialized, take that subregion of the
        # frame. Otherwise, take the bottom quarter of the frame if the
        # roi_flag is enabled, assuming a Wide 360p format (640x360).
        if self.template_roi:
            frame = frame[self.template_roi[0][1]:self.template_roi[1][1], :]
        elif self.roi_flag:
            frame = frame[270:, :]

        # Match the template using a normalized cross-correlation method and
        # retrieve the confidence and top-left points from the result.
        match_mat = cv2.matchTemplate(frame, self.pct_img,
            cv2.TM_CCORR_NORMED, mask=self.pct_mask)
        conf_list, tl_list = self.get_match_results(match_mat, num_results)

        # Compensate for point location if a region of interest was used.
        if self.template_roi:
            for i in range(num_results):
                tl_list[i] = (tl_list[i][0],
                    tl_list[i][1] + self.template_roi[0][1])
        elif self.roi_flag:
            for i in range(num_results):
                tl_list[i] = (tl_list[i][0], tl_list[i][1] + 270)

        # Create a list of bounding boxes (top-left & bottom-right points),
        # using the input template_shape given as (width, height).
        bbox_list = list()
        h, w = self.pct_img.shape[:2]
        for tl in tl_list:
            br = (tl[0] + w, tl[1] + h)
            bbox_list.append((tl, br))

        return conf_list, bbox_list


    # Take the result of cv2.matchTemplate, and find the most likely locations
    # of a template match. To find multiple locations, the region around a
    # successful match is zeroed. Return a list of confidences and locations.
    def get_match_results(self, match_mat, num_results):
        max_val_list, top_left_list = list(), list()
        match_mat_dims = match_mat.shape

        # Find multiple max locations in the input matrix using cv2.minMaxLoc
        # and then zeroing the surrounding region to find the next match.
        for _ in range(0, num_results):
            _, max_val, _, top_left = cv2.minMaxLoc(match_mat)
            set_subregion_to_zeros(match_mat, match_mat_dims,
                top_left, radius=self.template_match_radius)
            max_val_list.append(max_val)
            top_left_list.append(top_left)

        return(max_val_list, top_left_list)


    # Resize the original template a number of times to find the dimensions
    # of the template that yield the highest (optimal) confidence. Return the
    # bounding box, confidence value, and optimal template dimensions.
    def get_calibrate_results(self, frame):
        h, w = self.orig_pct_img.shape[:2]
        opt_max_val, opt_top_left, opt_w, opt_h = 0, 0, 0, 0

        # Assuming a Wide 360p format (640×360), only search the bottom quarter
        # of the input frame for the template if the roi_flag is enabled.
        if self.roi_flag:
            frame = frame[270:, :]

        # Iterate over a num. of widths, and rescale the img/mask accordingly.
        for new_w in range(self.calib_w_range[0], self.calib_w_range[1]):
            new_h = int(new_w * h / w)
            pct_img = cv2.resize(self.orig_pct_img, (new_w, new_h))
            pct_mask = cv2.resize(self.orig_pct_mask, (new_w, new_h))

            # Calculate the confidence and location of the current rescale.
            match_mat = cv2.matchTemplate(frame, pct_img,
                cv2.TM_CCORR_NORMED, mask=pct_mask)
            _, max_val, _, top_left = cv2.minMaxLoc(match_mat)

            # Store the results if the confidence is larger than the previous.
            if max_val > opt_max_val:
                opt_max_val, opt_top_left = max_val, top_left
                opt_w, opt_h = new_w, new_h

        # Compensate for point location if a region of interest was used.
        if self.roi_flag:
            opt_top_left = (opt_top_left[0], opt_top_left[1] + 270)

        # Format the bounding box and return.
        bbox = (opt_top_left, (opt_top_left[0]+opt_w, opt_top_left[1]+opt_h))
        return bbox, opt_max_val, opt_w, opt_h


    # Given a list of expected bounding boxes, return a region of interest
    # bounding box, that covers a horizontal line over the entire 360p frame.
    # The bottom y-coordinate must not surpass the boundaries of the frame.
    def get_template_roi(self, bbox_list):
        tol, y_min_list, y_max_list = self.roi_y_tolerance, list(), list()
        for bbox in bbox_list:
            y_min_list.append(bbox[0][1])
            y_max_list.append(bbox[1][1])
        y_min = max(0, min(y_min_list)-tol)
        y_max = min(359, max(y_max_list)+tol)
        return ((0, y_min), (639, y_max))


    # Given an initial guess of match ranges, make a more precise estimate.
    def get_precise_match_ranges(self, init_match_ranges):

        # Iterate through the match ranges, going backwards if at the start
        # of a match, and going forward if at the end of a match.
        prec_match_ranges_flat = list()
        init_match_ranges_flat = init_match_ranges.flatten()
        for i, fnum_prediction in enumerate(init_match_ranges_flat):
            fnum = fnum_prediction
            if i % 2 == 0:
                current_step_size = -self.prec_step_size
            else:
                current_step_size = self.prec_step_size

            while True:
                # Obtain the frame and get the pct confidences and locations.
                frame = util.get_frame(self.capture, fnum, self.gray_flag)
                confidence_list, _ = self.get_tm_results(frame, 1)

                # Increment the precise counter if no pct was found.
                if confidence_list[0] > self.conf_threshold:
                    prec_counter = 0
                else:
                    prec_counter += 1

                # Exit if there has been no percent found over multiple frames.
                if prec_counter == self.prec_step_threshold:
                    prec_match_ranges_flat.append(
                        fnum - current_step_size*(prec_counter+1))
                    break
                elif fnum == 0 or fnum == self.stop_fnum:
                    prec_match_ranges_flat.append(fnum)
                    break
                fnum = fnum + current_step_size

        # Return the match ranges as a list of pairs.
        return np.reshape(prec_match_ranges_flat, (-1, 2))


    #### PERCENT MATCHER RUNTIME METHODS ######################################

    # Selects a random number of frames to calibrate the percent template size.
    def initialize_template_scale(self):

        # Generate random frames to search for a proper template size.
        random_fnum_list = np.random.randint(low=self.start_fnum,
            high=self.stop_fnum, size=self.num_init_frames)
        opt_w_list, bbox_list = list(), list()

        for random_fnum in random_fnum_list:

            # Get the calibrated accuracy for the random frame.
            frame = util.get_frame(self.capture, random_fnum, self.gray_flag)
            bbox, opt_conf, opt_w, _ = self.get_calibrate_results(frame)

            # Store template info if confidence above an input threshold.
            if opt_conf > self.conf_threshold:
                opt_w_list.append(opt_w)
                bbox_list.append(bbox)

        # Calculate the Median of the optimal widths and rescale accordingly.
        opt_w = int(np.median(opt_w_list))
        h, w = self.orig_pct_img.shape[:2]
        opt_h = h*opt_w//w
        self.pct_img = cv2.resize(self.orig_pct_img, (opt_w, opt_h))
        self.pct_mask = cv2.resize(self.orig_pct_mask, (opt_w, opt_h))

        # Calculate the region of interest to search for the template.
        self.template_roi = self.get_template_roi(bbox_list)


    # Iterate through the video to identify when the percent sprite is present.
    def get_pct_timeline(self):

        pct_timeline = list()
        for fnum in range(self.start_fnum, self.stop_fnum, self.step_size):
            # Obtain the frame and get the template confidences and locations.
            frame = util.get_frame(self.capture, fnum, self.gray_flag)
            confidence_list, _ = self.get_tm_results(frame, 1)

            # Append to the percent timeline according to if percent was found.
            if confidence_list[0] > self.conf_threshold:
                pct_timeline.append(0)
            else:
                pct_timeline.append(-1)

        return pct_timeline


#### Functions not inherent by PercentMatcher Object ##########################

# Given an image location, extract the image and alpha (transparent) mask.
def get_image_and_mask(img_location, gray_flag):

    # Load image from file with alpha channel (UNCHANGED flag). If an alpha
    # channel does not exist, just return the base image.
    img = cv2.imread(img_location, cv2.IMREAD_UNCHANGED)
    if img.shape[2] <= 3:
        return img, None

    # Create an alpha channel matrix  with values between 0-255. Then
    # threshold the alpha channel to create a binary mask.
    channels = cv2.split(img)
    mask = np.array(channels[3])
    _, mask = cv2.threshold(mask, 250, 255, cv2.THRESH_BINARY)

    # Convert image and mask to grayscale or BGR based on input flag.
    if gray_flag:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    return img, mask


# Resize an image and mask based on an input scale ratio.
def resize_image_and_mask(img, mask, img_scale):
    h, w = img.shape[:2]
    h, w = int(h * img_scale), int(w * img_scale)
    resized_img = cv2.resize(img, (w, h))
    resized_mask = cv2.resize(mask, (w, h))
    return resized_img, resized_mask


# Take a matrix and coordinate, and set the region around that coordinate
# to zeros. This function also prevents matrix out of bound errors if the
# input coordinate is near the matrix border. Also, the input coordinate
# is organized as (row, column) while matrices are organized (x, y). Matrices
# are pass by reference, so the input can be directly modified.
def set_subregion_to_zeros(input_mat, mat_dims, center_pt, radius):

    # Set the top-left and bot-right points of the zeroed region. Note that
    # mat_dims is organized as (width, height) or (x-range,y-range).
    tl = (max(center_pt[1]-radius, 0),
          max(center_pt[0]-radius, 0))
    br = (min(center_pt[1]+radius+1, mat_dims[0]-1),
          min(center_pt[0]+radius+1, mat_dims[1]-1))

    # Calculate the size of the region to be zeroed. Initialize it as a square
    # of size (2r+1), then subtract off the region that is cutoff by a border.
    x_size, y_size = radius*2+1, radius*2+1
    if center_pt[1]-radius < 0:
        x_size -= radius-center_pt[1]
    elif center_pt[1]+radius+1 > mat_dims[0]-1:
        x_size -= center_pt[1]+radius+1 - (mat_dims[0]-1)
    if center_pt[0]-radius < 0:
        y_size -= radius-center_pt[0]
    elif center_pt[0]+radius+1 > mat_dims[1]-1:
        y_size -= center_pt[0]+radius+1 - (mat_dims[1]-1)

    input_mat[tl[0]:br[0], tl[1]:br[1]] = np.zeros((x_size, y_size))
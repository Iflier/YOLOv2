import time
import cv2
import numpy as np
from chainer import serializers, Variable
import chainer.functions as F
import argparse
from yolov2 import *
from lib.image_generator import *

item_path = "./items"
background_path = "./backgrounds"
weight_file = "./backup/yolov2_final.model"
label_file = "./data/label.txt"
input_height, input_width = (416, 416)
loop = 10
n_classes = 10
n_boxes = 5
detection_thresh = 0.5
iou_thresh = 0.3

# load image generator
print("loading image generator...")
generator = ImageGenerator(item_path, background_path)
animation = generator.generate_random_animation(loop=loop, bg_index=0, crop_width=input_width, crop_height=input_height, min_item_scale=1.0, max_item_scale=3.0)

# read labels
with open(label_file, "r") as f:
    labels = f.read().strip().split("\n")

# load model
print("loading model...")
model = YOLOv2Predictor(YOLOv2(n_classes=n_classes, n_boxes=n_boxes))
serializers.load_hdf5(weight_file, model) # load saved model
model.predictor.train = False
model.predictor.finetune = False

# init video writer
codec = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
video_writer = cv2.VideoWriter('output.avi', codec, 25.0, (input_width, input_height)) 

for frame in animation:
    orig_img = frame
    orig_img = cv2.resize(orig_img, (input_height, input_width))
    img = np.asarray(orig_img, dtype=np.float32) / 255.0
    img = img.transpose(2, 0, 1)

    # forward
    x_data = img[np.newaxis, :, :, :]
    x = Variable(x_data)
    x, y, w, h, conf, prob = model.predict(x)

    # parse result
    _, _, _, grid_h, grid_w = x.shape
    x = F.reshape(x, (n_boxes, grid_h, grid_w)).data
    y = F.reshape(y, (n_boxes, grid_h, grid_w)).data
    w = F.reshape(w, (n_boxes, grid_h, grid_w)).data
    h = F.reshape(h, (n_boxes, grid_h, grid_w)).data
    conf = F.reshape(conf, (n_boxes, grid_h, grid_w)).data
    prob = F.transpose(F.reshape(prob, (n_boxes, n_classes, grid_h, grid_w)), (1, 0, 2, 3)).data
    detected_indices = (conf * prob).max(axis=0) > detection_thresh

    results = []
    for i in range(detected_indices.sum()):
        results.append({
            "label": labels[prob.transpose(1, 2, 3, 0)[detected_indices][i].argmax()],
            "probs": prob.transpose(1, 2, 3, 0)[detected_indices][i],
            "conf" : conf[detected_indices][i],
            "objectness": conf[detected_indices][i] * prob.transpose(1, 2, 3, 0)[detected_indices][i].max(),
            "box"  : Box(
                        x[detected_indices][i]*input_width,
                        y[detected_indices][i]*input_height,
                        w[detected_indices][i]*input_width,
                        h[detected_indices][i]*input_height).crop_region(input_height, input_width)
            })

    # nms
    nms_results = nms(results, iou_thresh)

    # draw result
    for result in nms_results:
        left, top = result["box"].int_left_top()
        cv2.rectangle(
            orig_img,
            result["box"].int_left_top(), result["box"].int_right_bottom(),
            (0, 0, 255),
            2
        )
        text = '%s(%2d%%)' % (result["label"], result["probs"].max()*result["conf"]*100)
        cv2.putText(orig_img, text, (left, top-4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        print(text)

    cv2.imshow("w", orig_img)
    cv2.waitKey(1)

    video_writer.write(orig_img)
video_writer.release()

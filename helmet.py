import cv2
import numpy as np
import os
import imutils
from tensorflow.keras.models import load_model
import easyocr
import os 

ROOT_DIR = "./"

os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'

net = cv2.dnn.readNet("./models/yolov5-tiny.weights", "./models/yolov5-cfg.cfg")
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

img_dir = './images'
model = load_model('./models/model_v2.h5')
print('model loaded!!!')
COLORS = [(0,255,0),(0,0,255)]

layer_names = net.getLayerNames()
output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
 

fourcc = cv2.VideoWriter_fourcc(*"XVID")
writer = cv2.VideoWriter('./videos/output.avi', fourcc, 5,(888,500))


def helmet_or_nohelmet(helmet_roi):
    try:
        print("🔍 Helmet ROI shape before resizing:", helmet_roi.shape)

        helmet_roi = cv2.resize(helmet_roi, (224, 224))
        helmet_roi = np.array(helmet_roi, dtype='float32') / 255.0
        helmet_roi = helmet_roi.reshape(1, 224, 224, 3)

        prediction = model.predict(helmet_roi)[0][0]
        print(f"🎯 Helmet Prediction: {prediction}")

        return int(prediction)

    except Exception as e:
        print(f"❌ Error in helmet_or_nohelmet: {e}")
        return 0



def detect_plates(mode):
    print(f"🟢 Processing video: {mode}")

    if not os.path.exists(mode):
        print("🚨 Video file not found!")
        return {"error": "Invalid video file"}

    cap = cv2.VideoCapture(mode)

    if not cap.isOpened():
        print("🚨 Failed to open video!")
        return {"error": "Failed to open video"}

    frame_count = 0

    while cap.isOpened():
        frame_count += 1
        ret, img = cap.read()

        if not ret:
            print("⚠️ No more frames to read, exiting...")
            break

        img = imutils.resize(img, height=500)
        height, width = img.shape[:2]

        # YOLO Blob
        blob = cv2.dnn.blobFromImage(img, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
        net.setInput(blob)
        outs = net.forward(output_layers)

        confidences = []
        boxes = []
        classIds = []

        # Processing YOLO Outputs
        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]

                if confidence > 0.3:
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)

                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)

                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    classIds.append(class_id)

        indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)

        if len(indexes) == 0:
            print("🚨 No objects detected in frame")
            continue

        print(f"✅ Frame {frame_count}: Detected {len(indexes)} objects")

        for i in range(len(boxes)):
            if i in indexes:
                x, y, w, h = boxes[i]
                color = [int(c) for c in COLORS[classIds[i]]]

                if classIds[i] == 0:  # Bike
                    helmet_roi = img[max(0, y):max(0, y) + max(0, h) // 4, max(0, x):max(0, x) + max(0, w)]
                else:  # Number Plate
                    crop_img = img[y:y + h, x:x + w]
                    cv2.rectangle(img, (x, y), (x + w, y + h), color, 7)

                    x_h, y_h, w_h, h_h = x - 60, y - 350, w + 100, h + 100

                    if y_h > 0 and x_h > 0:
                        h_r = img[y_h:y_h + h_h, x_h:x_h + w_h]

                        helmet_status = helmet_or_nohelmet(h_r)
                        category = ['helmet', 'no-helmet'][helmet_status]
                        print(f"🟡 Helmet Status: {category}")

                        cv2.putText(img, category, (x, y - 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 2)
                        cv2.rectangle(img, (x_h, y_h), (x_h + w_h, y_h + h_h), (255, 0, 0), 10)

                        if category == 'no-helmet':
                            print("🚨 No helmet detected!")

                        if helmet_status != 0:
                            person_crop_path = os.path.join('./person', f'crop_{frame_count}.png')
                            plate_crop_path = os.path.join(img_dir, f'crop_{frame_count}.png')

                            cv2.imwrite(person_crop_path, h_r)
                            cv2.imwrite(plate_crop_path, crop_img)

                            print(f"📸 Saved Person Image: {person_crop_path}")
                            print(f"📸 Saved Plate Image: {plate_crop_path}")

        writer.write(img)
        cv2.imshow("Helmet Violation Detection", img)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    print("✅ Video Processing Completed!")
    writer.release()
    cap.release()
    cv2.destroyAllWindows()

    return True


# detect_plates('test_helmet_red.mp4')

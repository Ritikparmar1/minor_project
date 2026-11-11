
import cv2
from pathlib import Path

# Get XML file location
CASCADE_PATH = (
    Path(__file__).resolve().parent /
    "haarcascade_frontalface_default.xml"
)

# Load face detector
face_detector = cv2.CascadeClassifier(
    str(CASCADE_PATH)
)

# Check classifier
if face_detector.empty():
    raise RuntimeError(
        "Face detection XML file could not be loaded!"
    )


def detect_faces(image):

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    faces = face_detector.detectMultiScale(
        gray,
        scaleFactor=1.2,
        minNeighbors=5,
        minSize=(100, 100)
    )

    return gray, faces


def create_recognizer():

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    return recognizer

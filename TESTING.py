import tensorflow as tf
from tensorflow.keras.models import load_model
import numpy as np
from tensorflow.keras.preprocessing import image
import matplotlib.pyplot as plt
import pickle
import os
import sys

def test_single_image(image_path):
    """
    Test a single image with the trained poultry disease classifier
    """
    # Load the trained model and class names
    try:
        model = load_model('poultry_disease_classifier.h5')
        with open('class_names.pkl', 'rb') as f:
            class_names = pickle.load(f)
    except FileNotFoundError as e:
        print(f"Error: Required file not found - {e}")
        print("Make sure 'poultry_disease_classifier.h5' and 'class_names.pkl' are in the same directory")
        return
    
    # Check if image file exists
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found!")
        return
    
    # Image dimensions (should match training)
    img_width, img_height = 150, 150
    
    try:
        # Preprocess the image
        img = image.load_img(image_path, target_size=(img_width, img_height))
        img_array = image.img_to_array(img)
        img_array = img_array / 255.0  # Normalize
        img_array = np.expand_dims(img_array, axis=0)
        
        # Make prediction
        predictions = model.predict(img_array)
        predicted_class_idx = np.argmax(predictions[0])
        predicted_class = class_names[predicted_class_idx]
        confidence = predictions[0][predicted_class_idx]
        
        # Get top 3 predictions
        top_3_indices = np.argsort(predictions[0])[-3:][::-1]
        top_3_predictions = [
            (class_names[i], predictions[0][i]) 
            for i in top_3_indices
        ]
        
        # Display results
        print("\n" + "="*60)
        print("🐔 POULTRY DISEASE CLASSIFICATION RESULT")
        print("="*60)
        print(f"Image: {os.path.basename(image_path)}")
        print(f"Predicted Class: {predicted_class}")
        print(f"Confidence: {confidence:.4f} ({confidence*100:.2f}%)")
        print("\nTop Predictions:")
        for i, (class_name, prob) in enumerate(top_3_predictions, 1):
            print(f"  {i}. {class_name}: {prob*100:.2f}%")
        print("="*60)
        
        # Display image and probabilities
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Show original image
        ax1.imshow(img)
        ax1.set_title(f'Input Image\nPredicted: {predicted_class}\nConfidence: {confidence*100:.2f}%')
        ax1.axis('off')
        
        # Show probability distribution
        y_pos = np.arange(len(class_names))
        bars = ax2.barh(y_pos, predictions[0], align='center', alpha=0.7)
        ax2.set_yticks(y_pos)
        ax2.set_yticklabels(class_names)
        ax2.set_xlabel('Probability')
        ax2.set_title('Class Probabilities')
        ax2.invert_yaxis()
        
        # Highlight predicted class
        bars[predicted_class_idx].set_color('red')
        
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        print(f"Error processing image: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_model.py <image_path>")
        print("Example: python test_model.py test_image.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    test_single_image(image_path)

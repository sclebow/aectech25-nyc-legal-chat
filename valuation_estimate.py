import joblib
import pickle
import numpy as np
import os
import json




# 14.5- Create comprehensive prediction function for deployment
def predict_property_value(property_features_dict, 
                           model_path='./valuation_model/final_roi_property_model.joblib', 
                           features_path='./valuation_model/final_model_features.joblib'):
    """
    Predict property value from features dictionary

    Args:
        property_features_dict: Dictionary with feature names as keys
        model_path: Path to saved model
        features_path: Path to saved feature list

    Returns:
        Predicted property value in dollars
    """
    # Load model and features
    model = joblib.load(model_path)
    required_features = joblib.load(features_path)

    with open('./valuation_model/freq_mappings.json') as f:
        frequency_mappings = json.load(f)

    # Create feature array in correct order
    feature_values = []
    for feat in required_features:
        if feat in property_features_dict:
            if feat in frequency_mappings:
                freq_value = frequency_mappings[feat][str(property_features_dict[feat])]
                print(f'{feat} input as {property_features_dict[feat]} coded as {freq_value}')
                feature_values.append(freq_value)
            else:
                feature_values.append(property_features_dict[feat])
        else:
            feature_values.append(0)  # Default for missing features

    # Predict (returns log value)
    log_prediction = model.predict([feature_values])[0]

    # Convert back to dollars
    dollar_prediction = np.expm1(log_prediction)

    return dollar_prediction

features = joblib.load(os.path.join(os.getcwd(),'valuation_model','final_model_features.joblib'))
print(features)

feat_dict = {
    'LIVING_AREA': 4*9,
    'GROSS_AREA' : 4*9,
    'LAND_SF' : 4*9*1.5,
    'FULL_BTH' : 1,
    'CD_FLOOR' : 1,
    'BLDG_TYPE' : 0.3,
    'RES_FLOOR' : 1,
    'TT_RMS' : 6
}

model_path = './valuation_model/final_roi_property_model.joblib'
features_path = './valuation_model/final_model_features.joblib'

predict = predict_property_value(feat_dict, model_path, features_path)

print(predict)
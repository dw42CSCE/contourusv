import numpy as np
import pandas as pd
from scipy.io import wavfile
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from pathlib import Path
import argparse
import time


def has_columns(file_path, delimiter=','):
    with open(file_path, 'r') as f:
        first_line = f.readline()
    return delimiter in first_line


def load_annotation(predicted_labels, actual_labels):
    # Load the dataframes
    predicted_labels = pd.read_csv(predicted_labels, sep='\t')
    actual_labels = pd.read_csv(actual_labels, sep='\t')

    # Convert numerical values to 0.2f precision
    actual_labels = actual_labels.round(2)

    return predicted_labels, actual_labels


def evaluate_predictions(filename, sample_labels, predicted_sample_labels, total_samples):
    # Calculate TP, FP, TN, FN
    tp = np.sum((sample_labels == 1) & (predicted_sample_labels == 1))
    fp = np.sum((sample_labels == 0) & (predicted_sample_labels == 1))
    tn = np.sum((sample_labels == 0) & (predicted_sample_labels == 0))
    fn = np.sum((sample_labels == 1) & (predicted_sample_labels == 0))

    # Normalize TP, FP, TN, FN
    tp, fp, tn, fn = tp / total_samples, fp / \
        total_samples, tn / total_samples, fn / total_samples

    # Calculate metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision +
                                           recall) if (precision + recall) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

    print(f"TP: {tp}, FP: {fp}, TN: {tn}, FN: {fn}")
    print(
        f"Precision: {precision}, Recall: {recall}, F1 Score: {f1_score}, Specificity: {specificity}")

    return {"Filename": filename, "TP": tp, "FP": fp, "TN": tn, "FN": fn, "Precision": precision, "Recall": recall, "F1 Score": f1_score, "Specificity": specificity}


def get_sample_labels(audio_file, actual_labels, predicted_labels):
    # Load the WAV file
    sampling_rate, data = wavfile.read(audio_file)
    # Get the total number of samples
    total_samples = len(data)
    time_points = np.arange(total_samples) / sampling_rate
    # Initialize all samples as 0 and convert to NumPy array
    sample_labels = np.zeros(total_samples)
    # Initialize all predicted samples as 0 and convert to NumPy array
    predicted_sample_labels = np.zeros(total_samples)

    # Example label windows in seconds
    label_windows = [
        {'begin_time': row['begin_time'], 'end_time': row['end_time']}
        for _, row in actual_labels.iterrows()
    ]

    predicted_label_windows = [
        {'begin_time': row['begin_time'], 'end_time': row['end_time']}
        for _, row in predicted_labels.iterrows()
    ]
    # Convert time windows to sample indices
    for window in tqdm(label_windows, desc="Converting time windows to sample indices"):
        start_time = window['begin_time']
        end_time = window['end_time']
        # Mark as 1 for presence of the event
        sample_labels[(time_points >= start_time) &
                      (time_points < end_time)] = 1

    # Convert predicted time windows to sample indices
    for window in tqdm(predicted_label_windows, desc="Converting predicted time windows to sample indices"):
        start_time = window['begin_time']
        end_time = window['end_time']
        predicted_sample_labels[(time_points >= start_time) & (
            time_points < end_time)] = 1  # Mark as 1 for presence of the event
    return sample_labels, predicted_sample_labels, total_samples


def run_evaluation(experiment, trial, root_path):
    print(f"Evaluating {experiment} {trial} experiment...")
    evaluation_results = []
    durations = []
    files_path = Path(root_path) / experiment / trial
    audio_files = sorted(list(files_path.rglob(
        "*.wav")) + list(files_path.rglob("*.WAV")))
    predicted_files = sorted(
        list(Path(f'{root_path}/output/{experiment}/{trial}/contour_detections').rglob("*.csv")))
    annotation_files = sorted(
        list(Path(f'{root_path}/{experiment}/{trial}/ground_truth_annotations').rglob("*.csv")))

    # Check for matching files and process them
    for audio_file in audio_files:
        predicted = next(
            (p for p in predicted_files if p.stem in audio_file.stem), None)
        actual = next(
            (a for a in annotation_files if a.stem in audio_file.stem), None)

        if not actual:
            print(
                f"No matching annotation file for {audio_file.name}. Skipping.")
            continue

        print(f"Processing {audio_file.stem}...")
        sampling_rate, data = wavfile.read(audio_file)
        # Get the total number of samples
        total_samples = len(data)
        duration = total_samples / sampling_rate

        # Check for missing columns in actual or predicted files
        if not has_columns(actual, delimiter='\t'):
            print(f"No columns found in {actual}. Skipping.")
            continue

        if not has_columns(predicted, delimiter='\t'):
            print(f"No columns found in {predicted}. Filling with zeros.")
            evaluation_results.append({
                "Filename": Path(predicted).stem,
                "TP": 0, "FP": 0, "TN": 0, "FN": 0,
                "Precision": 0, "Recall": 0, "F1 Score": 0, "Specificity": 0
            })
            continue

        # Proceed with processing if columns are found
        predicted_labels, actual_labels = load_annotation(
            predicted, actual)
        sample_labels, predicted_sample_labels, total_samples = get_sample_labels(
            audio_file, actual_labels, predicted_labels)
        durations.append(duration)
        filename = Path(predicted).stem
        evaluation_results.append(evaluate_predictions(
            filename, sample_labels, predicted_sample_labels, total_samples))
        print(f"Saved {filename} to evaluation_results")

    # Create a DataFrame from the evaluation results
    results_df = pd.DataFrame(evaluation_results)

    # Calculate and display metrics
    print(f"{experiment} {trial} Evaluation")
    mean_precision = results_df['Precision'].mean()
    std_precision = results_df['Precision'].std()
    print(f'Mean Precision: {mean_precision:.2f} ± {std_precision:.2f}')
    mean_recall = results_df['Recall'].mean()
    std_recall = results_df['Recall'].std()
    print(f'Mean Recall: {mean_recall:.2f} ± {std_recall:.2f}')
    mean_f1_score = results_df['F1 Score'].mean()
    std_f1_score = results_df['F1 Score'].std()
    print(f'Mean F1 Score: {mean_f1_score:.2f} ± {std_f1_score:.2f}')
    mean_specificity = results_df['Specificity'].mean()
    std_specificity = results_df['Specificity'].std()
    print(
        f'Mean Specificity: {mean_specificity:.2f} ± {std_specificity:.2f}')
    # Add mean and standard deviation to the DataFrame
    results_df = results_df._append({
        'Filename': 'Mean ± Std',
        'Precision': f"{mean_precision:.2f} ± {std_precision:.2f}",
        'Recall': f"{mean_recall:.2f} ± {std_recall:.2f}",
        'F1 Score': f"{mean_f1_score:.2f} ± {std_f1_score:.2f}",
        'Specificity': f"{mean_specificity:.2f} ± {std_specificity:.2f}"
    }, ignore_index=True)
    
    results_dir = Path(f'{root_path}/output/{experiment}/{trial}/evaluation_results')
    results_dir.mkdir(parents=True, exist_ok=True)
    # Save the DataFrame to a CSV file
    results_df.to_csv(
        f'{results_dir}/Evaluation_ContourUSV_{experiment}_{trial}_Ground_Truth_Annotations.csv', sep='\t', index=False)
    print(
        f"Saved evaluation results to {results_dir}/Evaluation_ContourUSV_{experiment}_{trial}_Ground_Truth_Annotations.csv")
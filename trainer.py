import streamlit as st
import time
from bayes_opt import BayesianOptimization
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, timedelta
from helpers import fetch_historical_data, add_selected_ta_features, reorder_data, normalize_data, create_sequences, LSTMModel, train_model, model_loss

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Sidebar inputs
ticker = st.sidebar.text_input("Ticker", "SPY")
start_date = st.sidebar.date_input("Start Date", datetime.now() - timedelta(days=365 * 5))
end_date = st.sidebar.date_input("End Date", datetime.now() - timedelta(days=1))
seq_length = st.sidebar.slider("Sequence Length", min_value=1, max_value=200, value=60)

# Fetching and processing the data
@st.cache_data
def get_processed_data(ticker, start_date, end_date):
    data = fetch_historical_data(ticker, start_date, end_date)
    if data is None:
        return None, None, None
    data = add_selected_ta_features(data)
    data = reorder_data(data.dropna())
    # Split data into training and validation sets before normalizing
    train_data, valid_data = train_test_split(data, test_size=0.2, shuffle=False)
    # Normalize data
    train_data, train_scaler, original_train_data = normalize_data(train_data.values)
    valid_data, _, original_valid_data = normalize_data(valid_data.values)
    return train_data, valid_data, original_train_data, original_valid_data, train_scaler

train_data, valid_data, original_train_data, original_valid_data, train_scaler = get_processed_data(ticker, start_date, end_date)

# Create sequences
X_train, y_train = create_sequences(train_data, seq_length)
X_valid, y_valid = create_sequences(valid_data, seq_length)

X_train = torch.from_numpy(X_train).float().to(device)
y_train = torch.from_numpy(y_train).float().to(device)
X_valid = torch.from_numpy(X_valid).float().to(device)
y_valid = torch.from_numpy(y_valid).float().to(device)

input_dim = train_data.shape[1]

# Define the function we want to optimize
def optimize_model(hidden_dim, num_layers, learning_rate):
    hidden_dim = int(hidden_dim)
    num_layers = int(num_layers)
    model = LSTMModel(input_dim, hidden_dim, num_layers, input_dim).to(device)
    criterion = torch.nn.MSELoss(reduction='mean').to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    model, _ = train_model(model, X_train, y_train, 100, criterion, optimizer)
    valid_loss = model_loss(model, X_valid, y_valid, criterion)
    return -valid_loss  # We want to maximize the negative loss (i.e., minimize the loss)

# Define the bounds of the parameters we want to optimize
pbounds = {
    'hidden_dim': (1, 100),
    'num_layers': (1, 5),
    'learning_rate': (0.0001, 0.01),
}

optimizer = BayesianOptimization(
    f=optimize_model,
    pbounds=pbounds,
    verbose=2,
    random_state=1,
)

# Run the optimization
optimizer.maximize(init_points=10, n_iter=30)

best_params = optimizer.max['params']
best_params['hidden_dim'] = int(best_params['hidden_dim'])
best_params['num_layers'] = int(best_params['num_layers'])

# Show the best parameters with typing effect
st.markdown("### Best Parameters")

output_text = f"""
Hidden Dimension: {best_params['hidden_dim']}
Number of Layers: {best_params['num_layers']}
Learning Rate: {best_params['learning_rate']}
"""

typing_speed = 0.03  # Adjust the typing speed (in seconds) to control the effect

# Split the output into lines
lines = output_text.strip().split("\n")

# Simulate typing effect for each line
for line in lines:
    placeholder = st.empty()
    for char in line:
        placeholder.text(char)
        time.sleep(typing_speed)
    placeholder.text(line)  # Display the full line after typing
    st.write("")  # Add an empty line after each output line

# Train the model with the best parameters
best_model = LSTMModel(input_dim, best_params['hidden_dim'], best_params['num_layers'], input_dim).to(device)
criterion = torch.nn.MSELoss(reduction='mean').to(device)
optimizer = torch.optim.Adam(best_model.parameters(), lr=best_params['learning_rate'])
best_model, _ = train_model(best_model, X_train, y_train, 100, criterion, optimizer)
torch.save(best_model.state_dict(), 'best_model_weights.pth')  # Save the best model

# Show the loss on the validation set with typing effect
st.markdown("### Validation Loss")
valid_loss = model_loss(best_model, X_valid, y_valid, criterion)

output_text = f"{valid_loss:.4f}"

lines = output_text.strip().split("\n")

for line in lines:
    placeholder = st.empty()
    for char in line:
        placeholder.text(char)
        time.sleep(typing_speed)
    placeholder.text(line)
    st.write("")

# Load the best model
best_model = LSTMModel(input_dim, best_params['hidden_dim'], best_params['num_layers'], input_dim).to(device)
best_model.load_state_dict(torch.load('best_model_weights.pth'))
best_model.eval()

# Get the last sequence of data
last_sequence = torch.from_numpy(valid_data[-seq_length:].reshape(1, -1, input_dim)).float().to(device)

# Make a prediction
predicted_value = best_model(last_sequence)
predicted_value = predicted_value.cpu().detach().numpy()

# Rescale the predicted value
predicted_value = train_scaler.inverse_transform(predicted_value)

# Fetch the actual values
actual_values = original_valid_data[-1]

st.markdown("### Actual Values")

output_text = f"""
Open: {actual_values[0]:.2f}
High: {actual_values[1]:.2f}
Low: {actual_values[2]:.2f}
Close: {actual_values[3]:.2f}
"""

lines = output_text.strip().split("\n")

for line in lines:
    placeholder = st.empty()
    for char in line:
        placeholder.text(char)
        time.sleep(typing_speed)
    placeholder.text(line)
    st.write("")

st.markdown("### Predicted Next Values")

output_text = f"""
Open: {predicted_value[0][0]:.2f}
High: {predicted_value[0][1]:.2f}
Low: {predicted_value[0][2]:.2f}
Close: {predicted_value[0][3]:.2f}
"""

lines = output_text.strip().split("\n")

for line in lines:
    placeholder = st.empty()
    for char in line:
        placeholder.text(char)
        time.sleep(typing_speed)
    placeholder.text(line)
    st.write("")
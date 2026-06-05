import pickle
def saveFileAsDictionary(data, file_path):
    with open(file_path, 'wb') as file:
        pickle.dump(data, file)
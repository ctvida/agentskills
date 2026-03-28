import pandas as pd
# Load your modified CSV
df = pd.read_csv('drive_actions.csv')

def execute_actions(service, df):
    for index, row in df[df['approved'] == True].iterrows():
        if row['action'] == 'MOVE':
            # Logic to update file parents
            service.files().update(fileId=row['file_id'], 
                                   addParents=new_parent_id, 
                                   removeParents=row['current_parent']).execute()
        elif row['action'] == 'SHORTCUT':
            # Logic to move then create shortcut
            pass
        elif row['action'] == 'DELETE_DUPLICATE':
            # Logic to trash file
            service.files().trash(fileId=row['file_id']).execute()
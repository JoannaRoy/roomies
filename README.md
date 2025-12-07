## roomies

This repo has scripts to automate task tracking in our apartment -- for now it just makes weekly chores tasks in our notion, but maybe some more stuff will be added in the future if it makes sense.

how it works:
- every week, a github action runs
- it reads all the "chores" and "roomies" from each of their respective databases (via the notion API)
- then, it assigns a roomie to each chore, and creates a task for each of them (due one week from the time the script is run)
- it adds each task to the "to dos" database
- every roomie in our apartment has a 'view' in the database that shows 

notes/features:
- pulls from the "roomies" database, so adding a roommate there will automatically distribute tasks for them in future weeks
- similarly, adding a task to the "chores" database will automatically include it in the task distribution for future weeks
- tasks are assigned once per week (so whichever task/chore is assigned should be completed within that time)
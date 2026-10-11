# Frontend

React + TypeScript + Vite frontend for TutorBot, styled with Tailwind CSS.

The backend isn't connected yet, so the pages run on mock data:

- **Login**: any username and password works.
- **Home**: an overview and a list of your classes (one mock class, CS 5342 Network Security).
- **Tutor**: a chat that gives mock answers with citations.
- **Quiz**: generates a mock quiz, then grades it with feedback.

## Requirements

- [Node.js](https://nodejs.org/) 20.19+ or 22.12+ (npm is included)

## Running it

From the `frontend` folder:

```bash
npm install   # first time, and whenever package.json changes
npm run dev
```

Then open the URL it prints, usually http://localhost:5173. Saving a file updates the page automatically.

## Other commands

| Command | What it does |
|---|---|
| `npm run build` | Type-checks and builds a production version into `dist/` |
| `npm run preview` | Serves the `dist/` build locally to test it |
| `npm run lint` | Runs the linter (oxlint) |

## Project layout

```
src/
├── App.tsx            # Routes; pages that need a login sit inside LoggedInLayout
├── main.tsx           # App entry point
├── index.css          # Tailwind import
├── pages/             # Login, Home, Tutor, Quiz
├── components/        # Navbar, ClassCard, ThoughtLine (from React Bits)
├── assets/assets.ts   # Mock data: classes, tutor answers, quiz questions
└── utils/mockAgent.ts # Fakes the agent's progress steps until the backend exists
```

Spots that will call the backend later are marked with `// TODO` comments.

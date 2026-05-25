import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';

// Stylesheets are split by concern so adding a new primitive or a new
// page-specific rule has an obvious home. Import order is dependency
// order: tokens → resets → layout → primitives → page-specific.
import './styles/tokens.css';
import './styles/base.css';
import './styles/layout.css';
import './styles/primitives.css';
import './styles/pages.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);

import React from 'react';
import ReactDOM from 'react-dom/client';
import { Toaster } from 'react-hot-toast';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
    <Toaster
      position="top-right"
      toastOptions={{
        style: {
          background: '#13131f',
          color: '#f1f5f9',
          border: '1px solid rgba(124,58,237,0.3)',
          fontFamily: 'Inter, sans-serif',
          fontSize: '13px',
        },
        success: { iconTheme: { primary: '#10b981', secondary: '#08080f' } },
        error:   { iconTheme: { primary: '#f43f5e', secondary: '#08080f' } },
      }}
    />
  </React.StrictMode>
);

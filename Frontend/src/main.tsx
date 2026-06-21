import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App";
import CalendarPage from "./pages/CalendarPage";
import UploadPage from "./pages/UploadPage";
import AssistantPage from "./pages/AssistantPage";
import LandingPage from "./pages/LandingPage";
import CheckoutReturnPage from "./pages/CheckoutReturnPage";
import { BookingConfirmationModal } from "./components/calendar/BookingConfirmationModal";
import { PaymentModal } from "./components/calendar/PaymentModal";
import { CalendarEventsProvider } from "./context/CalendarEventsContext";
import { ChatSessionProvider } from "./context/ChatSessionContext";
import "./index.css";

// One generic greeting for the single shared chat thread (dashboard rail + the
// full-page assistant render the SAME conversation).
const CHAT_GREETING =
  "Hi — I'm your athlete assistant, wired into your training, recovery, match, schedule and sponsorship data. Ask me anything, or have me plan travel and booking for an upcoming event.";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <CalendarEventsProvider>
        <ChatSessionProvider greeting={CHAT_GREETING}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/landing" element={<LandingPage />} />
            <Route path="/dashboard" element={<App />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/upload/voice" element={<UploadPage />} />
            <Route path="/assistant" element={<AssistantPage />} />
            <Route path="/checkout/complete" element={<CheckoutReturnPage status="success" />} />
            <Route path="/checkout/cancelled" element={<CheckoutReturnPage status="cancelled" />} />
          </Routes>
          <PaymentModal />
          <BookingConfirmationModal />
        </ChatSessionProvider>
      </CalendarEventsProvider>
    </BrowserRouter>
  </StrictMode>
);

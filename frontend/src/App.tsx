import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard/Dashboard";
import Upload from "./pages/Upload/Upload";
import FloorPlanEditor from "./pages/FloorPlanEditor/FloorPlanEditor";
import Viewer3D from "./pages/Viewer3D/Viewer3D";
import Assistant from "./pages/Assistant/Assistant";
import Estimation from "./pages/Estimation/Estimation";
import Sustainability from "./pages/Sustainability/Sustainability";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/editor" element={<FloorPlanEditor />} />
        <Route path="/viewer" element={<Viewer3D />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/estimation" element={<Estimation />} />
        <Route path="/sustainability" element={<Sustainability />} />
      </Routes>
    </Layout>
  );
}

import React, { useState } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:5000";

function App() {
  const [password, setPassword] = useState("");
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [orders, setOrders] = useState([]);
  const [error, setError] = useState("");

  const login = async () => {
    setError("");
    try {
      const res = await axios.post(`${BACKEND_URL}/admin/login`, { password });
      setToken(res.data.token);
      localStorage.setItem("token", res.data.token);
      fetchOrders(res.data.token);
    } catch {
      setError("Mot de passe incorrect");
    }
  };

  const fetchOrders = async (jwtToken) => {
    try {
      const res = await axios.get(`${BACKEND_URL}/admin/orders`, {
        headers: { Authorization: `Bearer ${jwtToken}` },
      });
      setOrders(res.data);
    } catch {
      setError("Erreur lors de la récupération des commandes");
    }
  };

  const logout = () => {
    setToken("");
    setOrders([]);
    localStorage.removeItem("token");
  };

  if (!token) {
    return (
      <div style={{ padding: 20 }}>
        <h2>Connexion Admin</h2>
        <input
          type="password"
          placeholder="Mot de passe"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button onClick={login}>Se connecter</button>
        {error && <p style={{ color: "red" }}>{error}</p>}
      </div>
    );
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Tableau de bord des commandes</h2>
      <button onClick={logout}>Déconnexion</button>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <table border="1" cellPadding="5" style={{ marginTop: 20 }}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Nom</th>
            <th>Email</th>
            <th>Logo</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}>
              <td>{o.id}</td>
              <td>{o.name}</td>
              <td>{o.email}</td>
              <td>
                <img src={o.image_url} alt="logo" width={50} />
              </td>
              <td>{new Date(o.date).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;

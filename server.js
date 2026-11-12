const app = require("./api/index");

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`Durbar API running on port ${PORT}`);
});
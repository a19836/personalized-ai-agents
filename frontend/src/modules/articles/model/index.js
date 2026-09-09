export const articlesInitialState = {
  loading: true,
  error: "",
  items: []
};

export const editArticleInitialState = {
  loading: true,
  saving: false,
  error: "",
  title: "",
  body: ""
};

export const createArticleInitialState = {
  saving: false,
  error: "",
  articleId: "",
  title: "",
  body: ""
};

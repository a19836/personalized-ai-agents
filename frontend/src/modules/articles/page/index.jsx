import { useArticlesController } from "../controller/useArticlesController";
import { useCreateArticleController } from "../controller/useCreateArticleController";
import { useEditArticleController } from "../controller/useEditArticleController";
import ArticlesListView from "../view/ArticlesListView";
import CreateArticleView from "../view/CreateArticleView";
import EditArticleView from "../view/EditArticleView";

export function ArticlesPage() {
  const { state, remove } = useArticlesController();
  return <ArticlesListView state={state} onDelete={remove} />;
}

export function EditArticlePage() {
  const { state, setTitle, setBody, save, cancel } = useEditArticleController();
  return (
    <EditArticleView
      state={state}
      setTitle={setTitle}
      setBody={setBody}
      onSave={save}
      onCancel={cancel}
    />
  );
}

export function CreateArticlePage() {
  const { state, setArticleId, setTitle, setBody, create, cancel } =
    useCreateArticleController();
  return (
    <CreateArticleView
      state={state}
      setArticleId={setArticleId}
      setTitle={setTitle}
      setBody={setBody}
      onCreate={create}
      onCancel={cancel}
    />
  );
}

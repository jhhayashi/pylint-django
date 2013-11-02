from pylint.checkers.design_analysis import MisdesignChecker
from pylint.checkers.classes import ClassChecker
from pylint.checkers.newstyle import NewStyleConflictChecker
from astroid import InferenceError
from astroid.nodes import Class
from pylint.checkers.typecheck import TypeChecker
from pylint_django.utils import node_is_subclass
from pylint_plugin_utils import augment_visit, supress_message


def related_field_attributes(chain, node):
    """
    Pylint will raise an error when accesing a member of a ForeignKey
    attribute on a Django model. This augmentation supresses this error.
    """
    # TODO: if possible, infer the 'real' type of the foreign key attribute
    # by using the 'to' value given to its constructor
    related_fields = (
        'django.db.models.fields.related.ForeignKey',
        'django.db.models.fields.related.OneToOneField'
    )
    if node.last_child():
        try:
            for infered in node.last_child().infered():
                if infered.pytype() in related_fields:
                    return
        except InferenceError:
            pass

    chain()


def foreign_key_sets(chain, node):
    """
    When a Django model has a ForeignKey to another model, the target
    of the foreign key gets a '<modelname>_set' attribute for accessing
    a queryset of the model owning the foreign key - eg:

    class ModelA(models.Model):
        pass

    class ModelB(models.Model):
        a = models.ForeignKey(ModelA)

    Now, ModelA instances will have a modelb_set attribute.
    """
    if node.attrname.endswith('_set'):
        children = list(node.get_children())
        for child in children:
            try:
                inferred = child.infered()
            except InferenceError:
                pass
            else:
                for cls in inferred:
                    if node_is_subclass(cls, 'django.db.models.base.Model'):
                        # This means that we are looking at a subclass of models.Model
                        # and something is trying to access a <something>_set attribute.
                        # Since this could exist, we will return so as not to raise an
                        # error.
                        return
    chain()


def is_model_meta_subclass(node):
    if node.name != 'Meta' or not isinstance(node.parent, Class):
        return False

    return node_is_subclass(node.parent, 'django.db.models.base.Model') \
        or node_is_subclass(node.parent, 'django.forms.forms.Form')


def is_model_field_display_method(node):
    if not node.attrname.endswith('_display'):
        return
    if not node.attrname.startswith('get_'):
        return

    if node.last_child():
        # TODO: could validate the names of the fields on the model rather than
        # blindly accepting get_*_display
        for cls in node.last_child().infered():
            if node_is_subclass(cls, 'django.db.models.base.Model'):
                return True
    return False


def is_formview(node):
    return node_is_subclass(node, 'django.views.generic.edit.FormView')


def apply_augmentations(linter):
    augment_visit(linter, TypeChecker.visit_getattr, foreign_key_sets)
    augment_visit(linter, TypeChecker.visit_getattr, related_field_attributes)
    supress_message(linter, TypeChecker.visit_getattr, 'E1101', is_model_field_display_method)

    supress_message(linter, MisdesignChecker.visit_class, 'R0901', is_formview)

    supress_message(linter, NewStyleConflictChecker.visit_class, 'C1001', is_model_meta_subclass)
    supress_message(linter, ClassChecker.visit_class, 'W0232', is_model_meta_subclass)
    supress_message(linter, MisdesignChecker.leave_class, 'R0903', is_model_meta_subclass)

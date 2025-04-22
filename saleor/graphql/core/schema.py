import graphene

from .mutations import FileUpload


class CoreQueries(graphene.ObjectType):
    pass


class CoreMutations(graphene.ObjectType):
    file_upload = FileUpload.Field()

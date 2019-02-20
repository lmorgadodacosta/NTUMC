import os, sys, time, sqlite3
from collections import defaultdict as dd
from lxml import etree
import argparse

################################################################################
# TO DO
################################################################################
# - warn if requested docs do not exist, only get data for them
# - get chunks
# - get sentiment chunks
# - rename DTD to user_stamp time_stamp
# - 
################################################################################

def create_output(corpus):
    output = """<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Corpus SYSTEM "ntumc.dtd">"""
    output += etree.tostring(corpus, pretty_print=True).decode()

    return output


def dump_tree_to_file(output, filename='dump.xml'):
    with open(filename, 'w') as so:
        so.write(output)

    print('{} successfully created'.format(filename))

def inf_dd():
    return dd(inf_dd)

def valid_xml(c):
    codepoint = ord(c)
    # conditions ordered by presumed frequency
    return (
        0x20 <= codepoint <= 0xD7FF or
        codepoint in (0x9, 0xA, 0xD) or
        0xE000 <= codepoint <= 0xFFFD or
        0x10000 <= codepoint <= 0x10FFFF
        )

def main(db_path,docs):
    cwd = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(cwd, db_path)

    ################################################################################
    # CONNECT TO DB
    ################################################################################
    with sqlite3.connect(db_path) as con:
        c = con.cursor()
    ################################################################################

        c.execute("""SELECT docid,doc,title,url, subtitle, corpusID 
                     FROM doc
                  """)
        sql_docs = c.fetchall()

        c.execute("""SELECT sid, docID, pid, sent, comment, usrname 
                     FROM sent
                  """)
        sql_sents = c.fetchall()
        sents_by_doc_dd = dd(list)
        for s in sql_sents:
            sents_by_doc_dd[s[1]].append(s)

        c.execute("""SELECT sid, wid, word, pos, lemma, cfrom, cto, comment, usrname 
                     FROM word
                  """)
        sql_words = c.fetchall()
        words_by_sent_dd = dd(list)
        for w in sql_words:
            words_by_sent_dd[w[0]].append(w)

        c.execute("""SELECT sid, cid, clemma, tag, tags, comment, ntag, usrname
                     FROM concept
                  """)
        sql_concepts = c.fetchall()
        concepts_by_sent_dd = dd(list)
        for cc in sql_concepts:
            concepts_by_sent_dd[cc[0]].append(cc)

        c.execute("""SELECT sid, wid, cid, usrname
                     FROM cwl
                  """)
        sql_cwl = c.fetchall()
        cwl_by_sent_dd = dd(lambda: dd(list))
        for cwl in sql_cwl:
            sid, wid, cid, usrname = cwl
            cwl_by_sent_dd[sid][cid].append(wid)

        c.execute("""SELECT sid, cid, score, username
                     FROM sentiment
                  """)
        sql_senti = c.fetchall()
        senti_by_sent_dd = dd(lambda: dd(tuple))
        for (sid, cid, score, username) in sql_senti:
            senti_by_sent_dd[sid][cid] = (score, username)

        ################################################################################
        # BUILD THE XML
        ################################################################################

        corpus = etree.Element("Corpus")
        corpus.set("corpusID", "ntumc")
        corpus.set("title", "NTU Multilingual Corpus")
        corpus.set("language", "multilingual")
        for d in sql_docs:
            docid, docname, doctitle, docurl, docsub, doccoll = d
            if docname not in docs:
                continue
            doclang = "eng"

            document = etree.SubElement(corpus, "Document")
            document.set("docID", "d" + str(docid))
            document.set("doc", docname)
            document.set("language", doclang)
            document.set("title", doctitle)
            if docsub:
                document.set("subtitle", docsub)
            if docurl:
                document.set("url", docurl)
            if doccoll:
                document.set("collection", str(doccoll))

            for s in sents_by_doc_dd[docid]:

                sid, docID, pid, sent, comment, user = s

                sentence = etree.SubElement(document, "Sentence")
                sentence.set("sid", "s" + str(sid))
                try:
                    sentence.set("sent", sent)
                except:
                    cleaned_sent = ''.join(c for c in sent if valid_xml(c))
                    sentence.set("sent", cleaned_sent)
                if pid:
                    sentence.set("pid", str(pid))
                if comment:
                    sentence.set("comment", comment)
                if user:
                    sentence.set("last_changed_by", user)

                for w in words_by_sent_dd[sid]:

                    sid, wid, word_surf, pos, lemma, cfrom, cto, comment, user = w

                    word = etree.SubElement(sentence, "Word")
                    word.set("wid", "s" + str(sid) + "w" + str(wid))

                    try:
                        word.set("surface_form", word_surf)
                    except:
                        cleaned_word = ''.join(c for c in word_surf if valid_xml(c))
                        word.set("surface_form", cleaned_word)
                    if pos:
                        word.set("pos", pos)
                    if lemma:
                        word.set("lemma", lemma)
                    if cfrom:
                        word.set("cfrom", str(cfrom))
                    if cto:
                        word.set("cto", str(cto))
                    if comment:
                        word.set("comment", comment)
                    if user:
                        word.set("last_changed_by", user)

                for cc in concepts_by_sent_dd[sid]:
                    sid, cid, clemma, tag, tags, comment, ntag, user = cc

                    concept = etree.SubElement(sentence, "Concept")
                    concept.set("cid", "s" + str(sid) + "c" + str(cid))

                    wids = ""
                    for wid in cwl_by_sent_dd[sid][cid]:
                        wids += "s" + str(sid) + "w" + str(wid) + " "
                    wids = wids.strip()
                    concept.set("wid", wids)

                    if clemma:
                        concept.set("clemma", clemma)
                    if tag:
                        concept.set("synset_tag", tag)
                    if comment:
                        concept.set("comment", comment)
                    if user:
                        concept.set("last_changed_by", user)

                    if senti_by_sent_dd[sid][cid]:
                        score, username = senti_by_sent_dd[sid][cid]
                        if abs(score) > 100:
                            print("score too high!", sid, cid, score)
                        else:
                            score = round(score/100.0,2)
                        concept_tag = etree.SubElement(concept, "Tag")
                        concept_tag.set("category","sentiment")
                        concept_tag.set("value", str(score))
                        if username:
                            concept_tag.set("last_changed_by", username)
                # chunk = etree.SubElement(sentence, "Chunk")
                # chunk.set("chid","ch1")
                # chunk.set("wid","w2 w3")

                # chunk_tag = etree.SubElement(chunk, "Tag")
                # chunk_tag.set("category","sentiment")
                # chunk_tag.set("value","0.8")


    return corpus

if __name__ == '__main__':
    usage = "Correct usage: python dump_sqlite.py.py -d <path_to_db_file>"
    parser = argparse.ArgumentParser(description="Dumps given sqlite file to xml validated against ntumc.dtd")
    parser.add_argument("-d", "--database", help="database file")
    parser.add_argument("-o", "--output", help="output to file in current folder", action="store_true", default=False)
    parser.add_argument("--docs", help="list of docs to output", nargs="*", default=[])
    options = parser.parse_args()

    if options.database:
        db_path = options.database
        corpus = main(db_path,options.docs)
        output = create_output(corpus)

        if options.output:
            filename = os.path.basename(db_path).split(".sqlite")[0] + '.xml'
            dump_tree_to_file(output, filename)
    else:
        print(usage)
        sys.exit(0)

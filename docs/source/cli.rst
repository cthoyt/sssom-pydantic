########################
 Command Line Interface
########################

sssom_pydantic automatically installs the command ``sssom_pydantic``. See
``sssom_pydantic --help`` for usage details.

.. click:: sssom_pydantic.cli:main
    :prog: sssom_pydantic
    :show-nested:

Here's an end-to-end workflow for merging several SSSOM documents together, filtering to
an appropriate subset, and generating an OWL bridge.

.. code-block:: console

    $ sssom_pydantic subset \
        --input https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.tsv \
        --prefix CHMO \
        --target-prefix FIX \
        --standardize \
        --output biomappings-chmo-fix.sssom.tsv
    $ sssom_pydantic subset \
        --input https://github.com/nfdi-de/section-metadata-wg-onto/raw/refs/heads/main/sssom/data/positive.sssom.tsv \
        --prefix CHMO \
        --target-prefix FIX \
        --standardize \
        --output nfdi-chmo-fix.sssom.tsv
    $ sssom_pydantic merge \
       --input https://github.com/NFDI4Chem/rsc-cmo/raw/0e53ad96495576890c217ebdddac7fadc2e9e0b1/src/mappings/fix-mappings.sssom.tsv \
       --input nfdi-chmo-fix.sssom.tsv \
       --input biomappings-chmo-fix.sssom.tsv \
       --standardize \
       --merge-manual \
       --mapping-set-id https://example.org/chmo-fix.sssom.tsv \
       | sssom_pydantic bridge \
        --output chmo-fix-bridge.ofn

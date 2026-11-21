package org.mdp.hadoop.io;

import java.io.IOException;

import org.apache.giraph.io.EdgeReader;
import org.apache.giraph.io.formats.TextEdgeInputFormat;
import org.apache.hadoop.io.DoubleWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.InputSplit;
import org.apache.hadoop.mapreduce.TaskAttemptContext;

/**
 * Lee un grafo con pesos desde un TSV: origen \t destino \t peso.
 * Igual que TextNullTextEdgeInputFormat del Lab 8, pero guarda el peso.
 */
public class TextDoubleTextEdgeInputFormat extends TextEdgeInputFormat<Text, DoubleWritable> {

    private static final String SPLIT = "\t";

    public TextDoubleTextEdgeInputFormat() {
        super();
    }

    @Override
    public EdgeReader<Text, DoubleWritable> createEdgeReader(InputSplit is, TaskAttemptContext tac) throws IOException {
        return new TextDoubleTextEdgeReader();
    }

    public class TextDoubleTextEdgeReader extends TextEdgeReaderFromEachLineProcessed<String[]> {
        @Override
        protected Text getSourceVertexId(String[] campos) throws IOException {
            return new Text(campos[0]);
        }

        @Override
        protected Text getTargetVertexId(String[] campos) throws IOException {
            return new Text(campos[1]);
        }

        @Override
        protected DoubleWritable getValue(String[] campos) throws IOException {
            return new DoubleWritable(Double.parseDouble(campos[2]));
        }

        @Override
        protected String[] preprocessLine(Text t) throws IOException {
            String[] split = t.toString().split(SPLIT);
            if (split.length < 3) {
                throw new IOException("Error en la linea " + t.toString() + ". Se esperaba origen, destino y peso separados por tabulador.");
            }
            return split;
        }
    }
}

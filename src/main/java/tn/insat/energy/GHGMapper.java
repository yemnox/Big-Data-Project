package tn.insat.energy;
import org.apache.hadoop.io.DoubleWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;
import java.io.IOException;

public class GHGMapper extends Mapper<Object, Text, Text, DoubleWritable> {
    private Text propertyType = new Text();
    private DoubleWritable emissions = new DoubleWritable();

    public void map(Object key, Text value, Context context) throws IOException, InterruptedException {
        String line = value.toString();
        if (line.startsWith("Data Year")) return;
        String[] columns = line.split(",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)");
        
        if (columns.length > 24) {
            try {
                String type = columns[9].trim();
                String ghgVal = columns[24].trim();
                if (!type.isEmpty() && !ghgVal.isEmpty()) {
                    propertyType.set(type);
                    emissions.set(Double.parseDouble(ghgVal));
                    context.write(propertyType, emissions);
                }
            } catch (Exception e) {}
        }
    }
}